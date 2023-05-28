""" Classes and static methods for test groups and grades.

    Terminology used here:

    - verdict:str 'ACCEPTED', 'WRONG_ANSWER', etc. (in its long form)
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


short_verdict = {
    'ACCEPTED': 'AC',
    'WRONG_ANSWER': 'WA',
    'JUDGE_ERROR': 'JE',
    'TIME_LIMIT_EXCEEDED': 'TLE',
    'RUN_TIME_ERROR': 'RTE',
}
long_verdict = {v: k for k, v in short_verdict.items()}


def ancestors(paths):
    """Return the set of all ancestors of the given paths"""
    return set(str(ancestor) for p in paths for ancestor in Path(p).parents)


# pylint: disable=too-few-public-methods
class TestDataTree:
    """The tree for all testcases and testgroups of a problem (in fact, for a subset of the
    testcases of a problem).
    This forms a tree defined by self.children[node], leaves are testcases.
    Tree nodes are identified by strings,
    the root is self.root == '.' whose children (if they exist) are
    'sample' and 'secret'
    """

    def __init__(self, testcasepaths, testdata_settings=None):
        """testcasepaths is an iterable of strings

        testdata_settings is given as a dict for each(!) of the *internal* nodes,
        it was either set expliclty in testdata.yaml for the given
        testgroup or from ancestors as per speficication. The settings for
        and internal node may be the empty dict or None."""

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

        if testdata_settings is None:
            testdata_settings = {node: {} for node in self.children}
        else:
            assert set(testdata_settings.keys()) == set(self.children)

        # make sure testdata_settings are not None, but possibly an empty dictionary:
        self.testdata_settings = {k: v or {} for k, v in testdata_settings.items()}
        TestDataTree._set_defaults(self.testdata_settings)

    @staticmethod
    def _set_defaults(testdata_settings):
        DEFAULTS = {
            'on_reject': 'break',
            # 'grading': not implemented, so not set
            'grader_flags': '',
            'accept_score': '1',
            'reject_score': '0',
            # 'range': not implemented, so not set
        }
        for node, settings in testdata_settings.items():
            for key, default in DEFAULTS.items():
                if key not in settings:
                    settings[key] = default

    def get_settings(self, node):
        """Get the settings (as a dict) relevant for the given node, which can
        be a testcase or an internal node. This includes the default settings
        (from the specification) explicitly.
        """
        return self.testdata_settings[str(Path(node).parent) if node in self.leaves else node]


class Expectation:
    """The expectation of a testnode."""

    def __init__(self, verdicts=None, score_range=None):
        if verdicts is None:
            # never expect JUDGE_ERROR
            verdicts = ["ACCEPTED", "WRONG_ANSWER", "TIME_LIMIT_EXCEEDED", "RUN_TIME_ERROR"]
        self.verdicts = set(verdicts)
        if range is not None:
            self.score_range = score_range

    def __in__(self, judgement):
        """Judgement can be verdict:str, score:int, or a tuple (verdict, score).
        If score is specified, self must have the score_range attribute.
        """
        if isinstance(judgement, tuple):
            verdict, score = judgement
            assert hasattr(self, 'score_range')
            return verdict in self.verdicts and score in self.score_range
        if isinstance(judgement, str):
            return judgement in self.verdicts
        assert hasattr(self, 'score_range')
        return judgement in self.score_range


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

    def __setitem__(self, testcase: str, grade):
        """Set the grade for the given testcase to the given grade.

        grade can be just a verdict, like "ACCEPTED" or a grade like ("ACCEPTED", 1)
        If score is not given, infer it from the 'accept_score' setting
        """
        assert testcase in self.tree.leaves, f"Use setitem only for testcases, not {testcase}"
        assert self.grades[testcase] is None, f"Grade for {testcase} was already set"
        if isinstance(grade, str):
            score = self.tree.get_settings(testcase)[
                'accept_score' if grade == 'ACCEPTED' else 'reject_score'
            ]
            grade = (grade, score)
        self.grades[testcase] = grade
        self._infer_grade_upwards(testcase)

    def __getitem__(self, node: str):
        return self.grades[node]

    def verdict(self, node: str = None):
        """The final verdict for a node. If node is None, for the entire testcase."""
        if node == None:
            node = self.tree.root
        return self.grades[node][0]

    def score(self):
        """The final grade for a node. If node is None, for the entire testcase."""
        if node == None:
            node = self.tree.root
        return self[self.tree.root][1]

    def _set_expectations(self, expectations, node):
        """Recursively transfer the given expectations (typically from a yaml dict)
        to the testdatatree rooted at the given node.

        In the simplest case, expectations is just a string "ACCEPTED".
        But it can be a set of verdicts or a nested dict as well.
        """

        if isinstance(expectations, dict):
            expected_verdicts = expectations.get('verdict')  # could be None or a list
            for testgroup in expectations:  # 'sample', 'secret', 'edgecases', ...
                if testgroup in ['verdict', 'score']:
                    continue
                longgroupname = str(Path(node) / Path(testgroup))
                if not longgroupname in self.tree.nodes:
                    warn(f"Found expected grade for {longgroupname}, but no testcases")
                self._set_expectations(expectations[testgroup], longgroupname)
        elif isinstance(expectations, str):
            expected_verdicts = [expectations]
        else:
            expected_verdicts = expectations  # expecations is a list

        if expected_verdicts is not None:
            self.expectations[node].verdicts &= set(expected_verdicts)
        # TODO set ranges for scores

    def _infer_expectations(self, node):
        """Visit self.tree from given internal tesddatatree node and infer expecations downwards.

        The following inference rules are implemented:

        1.  If the expected verdicts of the given node is the singleton {'ACCEPTED'} and
            and the grader flag is neither `accept_if_any_accepted` nor `always_accept`
            then all its children inherit the expectation {'ACCEPTED'}.
            If node is the root, and `ignore_sample` is set, `sample` is excempt from this.
        2.  (Nothing else so far. Could do some cool stuff with error sets, but not
            worth it because on_reject: break, the default, invalidates many inference rules)

        """
        tree = self.tree
        if node in tree.leaves:
            return

        grader_flags = tree.get_settings(node).get('grader_flags')
        inherit_accepted = (self.expectations[node].verdicts == set(['ACCEPTED'])) and (
            grader_flags is None
            or ('accept_if_any_accepted' not in grader_flags or 'always_accept' not in grader_flags)
        )
        for child in tree.children[node]:
            if inherit_accepted and not (
                node == tree.root and 'ignore_sample' in tree.get_settings(node)
            ):
                self.expectations[child].verdicts &= set(['ACCEPTED'])
                if len(self.expectations[child].verdicts) == 0:
                    error(f"No verdict possible for {child}")
            self._infer_expectations(child)

    def _infer_grade_upwards(self, node):
        """For a node that just changed its grades[node] (from None to a grade), check if this
        has consequences for its ancestors, and if so, infer grades upwards.

        We only do so if *all* chilren of a node have grades.
        Improve me by
        - considering the `on_reject` setting
        - implementing topsort properly
        """
        if node == self.tree.root:
            return
        parent = str(Path(node).parent)
        if self[parent] is not None:
            error(f"Grade for {parent} inferred from {node} was already inferred")
            # above logic could be different if we shortcut grading bc first_error etc
        siblings = self.tree.children[parent]
        if all(self[node] is not None for node in siblings):
            grades = [self[node] for node in siblings]
            self.grades[parent] = aggregate(parent, grades, settings=self.tree.get_settings(parent))
            self._infer_grade_upwards(parent)

    def _rec_prettyprint_tree(self, node, paddinglength, depth, prefix: str = ''):
        if depth <= 0:
            return
        subgroups = list(
            sorted(child for child in self.tree.children[node] if child not in self.tree.leaves)
        )
        branches = ['├─ '] * (len(subgroups) - 1) + ['└─ ']
        for branch, child in zip(branches, subgroups):
            if child not in self.tree.leaves:
                grade = self.grades[child][0]
                msg = None
                if self.expectations is not None:
                    expectations = self.expectations.get(child)
                    if expectations is not None:
                        if short_verdict[grade] in expectations:
                            color = Fore.GREEN
                        else:
                            color = Fore.RED
                            msg = f"Expected {expectations}"
                    else:
                        color = Fore.YELLOW
                else:
                    color = Fore.YELLOW
                print(
                    f"{prefix + branch + child.name:{paddinglength}}",
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
            3 * (len(node.parts)) + len(node.name)
            for node in self.tree.children
            if node not in self.tree.leaves and len(node.parts) <= maxdepth
        )
        self._rec_prettyprint_tree(self.tree.root, paddinglength, maxdepth)


def aggregate(path, grades, settings):
    """Given a list of grades, determine the default grader's grade per testgroup."""
    if not grades:
        log(f'No grades on {path}, so no graders ran')
        return ('ACCEPTED', 0)

    verdict, score = call_default_grader(
        grades, grader_flags=settings.get("grader_flags") if settings is not None else None
    )
    return verdict, score


def call_default_grader(grades, grader_flags=None):
    """Run the default grader to aggregate the given grades;
    this involves translating from 'ACCEPTED' to 'AC' and back.

    grades is a list of tuples of verdicts and scores, like [("ACCEPTED", 42), ("WRONG_ANSWER", 0)]

    SPEC-BREAKING CHANGE: assumes scores are integers, silently rounds down to nearest integer
    """

    grader_input = '\n'.join(f"{short_verdict[v]} {s}" for v, s in grades)
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
        return ('JUDGE_ERROR', None)

    ret = grader.returncode
    if ret != 0:
        error('Judge error: exit code %d for grader %s, expected 0' % (ret, grader))
        debug('Grader input: %s\n' % grader_input)
        return ('JUDGE_ERROR', None)

    grader_output_re = r'^((AC)|(WA)|(TLE)|(RTE)|(JE))\s+-?[0-9.]+\s*$'
    if not re.match(grader_output_re, grader_output):
        error('Judge error: invalid format of grader output')
        debug('Output must match: "%s"' % grader_output_re)
        debug('Output was: "%s"' % grader_output)
        return ('JUDGE_ERROR', None)

    verdict, score = grader_output.split()
    return long_verdict[verdict], float(score)
