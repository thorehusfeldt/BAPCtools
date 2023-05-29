""" Classes and static methods for test groups and grades.

    Terminology used here:

    - verdict one of 'AC', 'WA', 'TLE', 'RTE', or 'JE'
    - score:float a number
    - grade: a tuple of (verdict, score)

    - testdatatree: the tree given by the full filenames in data
    - testgroup: an *internal* node in the test data tree (spec is unclear about this)
    - testcase: a leaf of the test data tree

    The verdict at the root of the testdatatree is the final verdict of the
    default grader on all the testdata.
"""

import re
import subprocess
from pathlib import Path

from util import log, warn, error, debug

# pylint: disable = import-error
from colorama import Fore, Style
import config


def ancestors(paths):
    """Return the set of all ancestors of the given paths"""
    return set(str(ancestor) for p in paths for ancestor in Path(p).parents)

class Grade:
    def __init__(self, verdict, score=0):
        self.verdict = verdict
        self.score = score

    def __str__(self):
        res = self.verdict
        if self.verdict == "AC":
            res += f"({self.score:.0f})"
        return res


    def __repr__(self):
        return repr(self.verdict) + repr(self.score)

    def __eq__(self, other):
        return self.score == other.score and self.verdict == other.verdict

# pylint: disable=too-few-public-methods
class TestDataTree:
    """The tree for all testcases and testgroups of a problem (in fact, for a subset of the
    testcases of a problem).
    This forms a tree defined by self.children[node], leaves are testcases.
    Tree nodes are identified by strings,
    the root is self.root == '.' whose children (if they exist) are
    'sample' and 'secret'
    """

    def __init__(self, testcasepaths, settings=None):
        """testcasepaths is an iterable of strings

        settings is given as a dict for some(!) of the *internal* nodes,
        it was either set expliclty in testdata.yaml for the given
        testgroup or from ancestors as per speficication. From this, the
        testdata for every internal node is inferred using the inheritance
        logic implemented in verifyproblem.
        """

        self.root = '.'

        # Build tree structure of testcases and test(sub)groups
        self.leaves = set(testcasepaths)
        self.children = {node: [] for node in ancestors(self.leaves)}
        self.nodes = self.leaves | set(self.children.keys())
        for node in self.nodes:
            if node != self.root:
                self.children[str(Path(node).parent)].append(node)
        # sort all children lexicographically; this is important for grading choices such as
        # first_error, ignore_sample
        for node in self.children:
            self.children[node].sort()

        # Determine the settings for every internal node
        if settings is None:
            settings = {}
        defaults = {
            'on_reject': 'break',
            # 'grading': not implemented, so not set
            'grader_flags': '',
            'accept_score': '1',
            'reject_score': '0',
            'range': '-inf inf'
            # '{input, output}_validator_flags': not relevant for grading, so not set
        }

        self.settings = {'.': defaults | (settings.get('.') or {})}
        for node in iter(self):
            if node in self.leaves or node == '.':
                continue
            parent = TestDataTree.parent(node)
            self.settings[node] = self.settings[parent] | (settings.get(node) or {})

    def __iter__(self):
        """Iterate over the nodes in bfs-order and alphabetically:
        ('.', 'sample', 'secret', 'sample/1'...)
        """
        queue = ['.']
        for node in queue:
            yield node
            if node not in self.leaves:
                for child in self.children[node]:
                    queue.append(child)

    @staticmethod
    def parent(node):
        """The parent of a node; '.' is the root."""
        return str(Path(node).parent)

    def get_settings(self, node):
        """Get the settings (as a dict) relevant for the given node, which can
        be a testcase or an internal node.
        """
        return self.settings[TestDataTree.parent(node) if node in self.leaves else node]


class Expectation:
    """The expectation of a testnode."""

    def __init__(self, verdicts=None, score_range=None):
        self.verdicts = set(verdicts or ["AC", "WA", "TLE", "RTE"])
        self.score_range = score_range or "-inf inf"

    def __contains__(self, judgement):
        """Judgement can be verdict:str or a Grade,
        where score can be int, float, or even str
        """
        if isinstance(judgement, Grade):
            verdict = judgement.verdict
            lo, hi = map(float, self.score_range.split())
            score_ok = lo <= float(judgement.score) <= hi
        else:
            verdict = judgement
            score_ok = True

        return verdict in self.verdicts and score_ok

    def __repr__(self):
        return str(f"{self.verdicts} {self.score_range}")

    def __str__(self):
        if len(self.verdicts) == 1:
            res = next(iter(self.verdicts))
            if res == 'AC':
                res.append('(' + '..'.join(res.score.split()) + ')')
        else:
            res = str(self.verdicts)
        return res


class Grades:
    """Expectations and grades, typically for a specific submission and set of testcases.

    Initially, no grades are known; when a grade is known (typically when a submission is run),
    set it with self.grade[testcase] = (verdict, score) or self.set_verdict[testcase] = verdict.
    When all testcases are graded (possibly even earlier), self.grade.verdict() has final verdict

    self[node]  maps strings to tuples (verdict, score)
    self.verdict(node) and self.score(node) access the components
    """

    def __init__(self, testcases, expectations=None, testdata_settings=None):
        """
        expectations is typically from a yaml file, see _set_expectations

        testdata_settings maps every internal node to either None or a dict of
        settings that were explicitly given in `testdata.yaml` for that
        node or an ancestor of it. (But it does not specify the default settings
        from the specification.)
        """
        self.tree = TestDataTree(testcases, testdata_settings)
        self.expectations = {node: Expectation() for node in self.tree.nodes}
        if expectations is not None:
            self._set_expectations(expectations, self.tree.root)
            self._infer_expectations(self.tree.root)
        self.grades: int = {node: None for node in self.tree.nodes}

    def __setitem__(self, testcase, grade):
        """Set the grade for the given testcase to the given grade.

        grade can be just a verdict, like "AC" or a grade like ("AC", 1)
        If score is not given, infer it from the 'accept_score' setting
        """
        _ = list(self.set_grade(testcase, grade))

    def set_grade(self, testcase, grade):
        """ The default way of setting a testcase to a grade.

        grade is either a Grade object of a string.

        Returns an iterator of triples of the form

            (testcase_, grade_, was_expected)

        These contain the inferred grades from testcase and upwards.
        """
        if not testcase in self.tree.leaves:
            raise KeyError(f"Use __setitem__ only for testcases, not {testcase}")
        if self.grades[testcase] is not None:
            raise ValueError(f"Grade for {testcase} was already set")
        if isinstance(grade, str):
            score = self.tree.get_settings(testcase)[
                'accept_score' if grade == 'AC' else 'reject_score'
            ]
            grade = Grade(grade, score)
        self.grades[testcase] = grade
        yield (testcase, grade)
        yield from self._infer_grade_upwards(testcase)

    def __getitem__(self, node: str) -> Grade:
        return self.grades[node]

    def verdict(self, node: str = None) -> str:
        """The final verdict for a node. If node is None, for the root.

        Returns None if no grade has (yet) been determined.
        """
        if node is None:
            node = self.tree.root
        return self.grades[node].verdict if self.grades[node] is not None else None

    def score(self, node: str = None) -> float:
        """The final grade for a node. If node is None, for the root.

        Returns None if no grade has (yet) been determined.
        """
        if node is None:
            node = self.tree.root
        return self[node].score if self.grades[node] is not None else None

    def is_accepted(self, node=None):
        """Does the given node have an accepted verdict? If node is None, for the root. """
        if node is None:
            node = self.tree.root
        return self.grades[node] is not None and self.grades[node].verdict == 'AC'

    def is_rejected(self, node=None):
        """Does the given node have a rejected verdict? If node is None, for the root. """
        if node is None:
            node = self.tree.root
        return self.grades[node] is not None and self.grades[node].verdict != 'AC'

    def is_expected(self, node=None):
        if node is None:
            node = self.tree.root
        if self.grades[node] is None:
            raise ValueError(f"No grade determined for {node}")
        return self.grades[node] in self.expectations[node]

    def _set_expectations(self, expectations, node):
        """Recursively transfer the given expectations (typically from a yaml dict)
        to the testdatatree rooted at the given node.

        In the simplest case, expectations is just a string "AC".
        But it can be a list of verdicts or a nested dict as well.
        """

        if isinstance(expectations, dict):
            verdicts_for_node = expectations.get('verdict')  # could be None, str, or ist
            for testgroup in expectations:  # 'sample', 'secret', 'edgecases', ...
                if testgroup in ['verdict', 'score']:
                    continue
                longgroupname = str(Path(node) / Path(testgroup))
                if not longgroupname in self.tree.nodes:
                    warn(f"Found expected grade for {longgroupname}, but no testcases")
                self._set_expectations(expectations[testgroup], longgroupname)
        else:
            verdicts_for_node = expectations

        if verdicts_for_node is not None:
            if isinstance(verdicts_for_node, str):
                verdicts_for_node = [verdicts_for_node]

            self.expectations[node].verdicts &= set(verdicts_for_node)
            if self.expectations[node].verdicts == set():
                raise ValueError(f"Expectations cannot be the empty set, got {expectations}")
        # TODO set ranges for scores from testdata and expectations

    def _infer_expectations(self, node):
        """Visit self.tree from given internal tesddatatree node and infer expecations downwards.

        The following inference rules are implemented:

        1.  If the expected verdicts of the given node is the singleton {'AC'} and
            and the grader flag is neither `accept_if_any_accepted` nor `always_accept`
            then all its children inherit the expectation {'AC'}.
            If node is the root, and `ignore_sample` is set, `sample` is excempt from this.
        2.  (Nothing else so far. Could do some cool stuff with error sets, but not
            worth it because on_reject: break, the default, invalidates many inference rules)

        """
        tree = self.tree
        if node in tree.leaves:
            return

        grader_flags = tree.get_settings(node)['grader_flags']
        inherit_accepted = (self.expectations[node].verdicts == set(['AC'])) and (
            'accept_if_any_accepted' not in grader_flags or 'always_accept' not in grader_flags
        )
        for child in tree.children[node]:
            if inherit_accepted and not (
                node == tree.root and 'ignore_sample' in tree.get_settings(node)
            ):
                self.expectations[child].verdicts &= set(['AC'])
                if len(self.expectations[child].verdicts) == 0:
                    error(f"No verdict possible for {child}")
            self._infer_expectations(child)

    def _infer_grade_upwards(self, node):
        """For a node that just changed its grades[node] (from None to a grade), check if this
        has consequences for its ancestors, and if so, infer grades upwards.

        Note that `accept_if_any_accepted` cannot be graded just on the basis of a single
        accepted verdict (because the score may be different)
        """
        if node == self.tree.root:
            return
        parent = TestDataTree.parent(node)
        siblings = self.tree.children[parent]
        settings = self.tree.settings[parent]
        first_error_idx = min(
            (i for i, sib in enumerate(siblings) if self.is_rejected(sib)),
            default=len(siblings),
        )
        if (
            all(self[sib] is not None for sib in siblings)
            or settings['on_reject'] == 'break'
            and all(self.is_accepted(sib) for sib in siblings[:first_error_idx])
        ):
            grades = [self[sib] for sib in siblings if self[sib] is not None]
            aggregated_grade = aggregate(parent, grades, settings=self.tree.get_settings(parent))

            if self[parent] is not None:
                if self[parent] != aggregated_grade:
                    raise ValueError(
                        f"Grade {aggregated_grade} for {parent} inferred from {node} already set to {self[parent]}"
                    )
            else:
                self.grades[parent] = aggregated_grade
                yield (parent, aggregated_grade)
                yield from self._infer_grade_upwards(parent)

    def _rec_prettyprint_tree(self, node, paddinglength, depth, prefix: str = ''):
        if depth <= 0:
            return
        subgroups = list(
            sorted(child for child in self.tree.children[node] if child not in self.tree.leaves)
        )
        branches = ['├─ '] * (len(subgroups) - 1) + ['└─ ']
        for branch, child in zip(branches, subgroups):
            if child not in self.tree.leaves:
                grade = self.grades[child].grade
                msg = None
                if self.expectations is not None:
                    expectations = self.expectations.get(child)
                    if expectations is not None:
                        if grade in expectations:
                            color = Fore.GREEN
                        else:
                            color = Fore.RED
                            msg = f"Expected {expectations}"
                    else:
                        color = Fore.YELLOW
                else:
                    color = Fore.YELLOW
                print(
                    f"{prefix + branch + child:{paddinglength}}",
                    f"{color}{self.grades[child]}{Style.RESET_ALL}",
                    end=' ',
                )
                print(msg or "")
                extension = '│  ' if branch == '├─ ' else '   '
                self._rec_prettyprint_tree(
                    child, paddinglength, depth - 1, prefix=prefix + extension
                )

    def prettyprint_tree(self, maxdepth=3):
        """Print verdicts for the internal nodes of the graded testdata tree"""
        if maxdepth == 0:
            return
        paddinglength = max(
            3 * (len(Path(node).parts)) + len(node)
            for node in self.tree.children
            if node not in self.tree.leaves and len(Path(node).parts) <= maxdepth
        )
        self._rec_prettyprint_tree(self.tree.root, paddinglength, maxdepth)


def aggregate(path, grades, settings):
    """Given a list of grades, determine the default grader's grade per testgroup."""
    if not grades:
        log(f'No grades on {path}, so no graders ran')
        return ('AC', 0)

    if settings['on_reject'] == 'break':
        first_rejection = min(
            (i for (i, grade) in enumerate(grades) if grade.verdict != "AC"), default=None
        )
        if first_rejection is not None:
            grades = grades[: first_rejection + 1]
    return call_default_grader(grades, grader_flags=settings["grader_flags"])


def call_default_grader(grades, grader_flags=None):
    """Run the default grader to aggregate the given grades;

    grades is a list of Grade objects
    """

    grader_input = '\n'.join(f"{g.verdict} {g.score}" for g in grades)
    grader_flag_list = grader_flags.split() if grader_flags is not None else []

    grader = subprocess.Popen(
        [config.tools_root / 'support' / 'default_grader.py'] + grader_flag_list,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )

    try:
        grader_output, _ = grader.communicate(input=grader_input, timeout=1)
    except subprocess.TimeoutExpired:
        error('Judge error: Grader timed out')
        debug('Grader input: %s\n' % grader_input)
        return ('JE', None)

    ret = grader.returncode
    if ret != 0:
        error('Judge error: exit code %d for grader %s, expected 0' % (ret, grader))
        debug('Grader input: %s\n' % grader_input)
        return ('JE', None)

    grader_output_re = r'^((AC)|(WA)|(TLE)|(RTE)|(JE))\s+-?[0-9.]+\s*$'
    if not re.match(grader_output_re, grader_output):
        error('Judge error: invalid format of grader output')
        debug('Output must match: "%s"' % grader_output_re)
        debug('Output was: "%s"' % grader_output)
        return ('JE', None)

    verdict, score = grader_output.split()
    return Grade(verdict, float(score))
