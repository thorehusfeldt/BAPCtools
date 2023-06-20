"""Classes and static methods for test groups and grades,
using the default grader.

Terminology
-----------
verdict
    one of the strings 'AC', 'WA', 'TLE', 'RTE', or 'JE'

score
    a number, float

grade
    a tuple of (verdict, score); score may be None for a testcase.

gradeable
    A testcase or a testroup, i.e., something that can have a grade.

testdata
    The simple directed acyclic graph whose leaves are testcases.
    The testdata without the leaves form a rooted tree.

testcase
    A leaf in the testdata.
    Testcases have unique names like 'empty-graph' or '012-random-max_n';
    they may not contain '/'.
    The predecessors of a testcase are testgroups, but not the root.

testgroup
    An internal node in the testdata. The testgroups for a rooted
    tree. The root has one or two children, which are called 'sample'
    and 'secret'. The names of all other testgroups, if they exist,
    describe their position in the testdata tree, such as 'secret/group1'
    or 'secret/connected/cycles'.


Notes
-----

The conventions here are both more and less restrictive than the specification.

They are *more* restrictive in the sense that each testcase has a unique (short)
name. For instance, 'sample/1' and 'secret/1' refer to the same testcase, namely
testcase '1'. Every testcase is graded at most once. This follows the practice
of reusing testcases in other testgroups, for instance including all sample
instances in the secret instances or including testgroups in other testgroups.

They are *less* restrictive because not both 'sample' and 'secret' need to exist.
Such situations arise during problem development, when a submission is run against
only a subset of testcases.

"""

import re
import subprocess
from pathlib import Path
from functools import lru_cache

from util import log, error, debug
from expectations import Expectations

# pylint: disable = import-error
from colorama import Fore, Style
import config


def ancestors(paths):
    """Return the set of all ancestors of the given paths"""
    return set(ancestor for path in paths for ancestor in path.parents)


# pylint: disable=too-few-public-methods
class TestData:
    """The structure of testcases and testgroups of a problem."""

    # Internally, testgroups are identified by Path objects; the root is Path()
    # whose children (if they exist) are the testgroups Path('sample') and Path('secret').
    # All other testgroup paths start with 'sample/' or 'secret/'

    def __init__(self, cases, settings=None):
        """See Grades.__init__()"""

        self.root = Path()
        casepaths = sorted(Path(tc) for tc in cases)

        self.cases: list[str] = sorted(tp.name for tp in casepaths)

        # The testgroups containing a testcase
        self.groups_for_case: dict[str, list[Path]] = {tc: [] for tc in self.cases}

        # The testgroups and testcases contained in a testgroup, in alphabetic order.
        # Testgroups have type Path, testcases have type str.
        self.gradeables_for_group: dict[Path, list[Path | str]] = {
            path: [] for path in ancestors(casepaths)
        }

        for path in casepaths:
            self.groups_for_case[path.name].append(path.parent)
            self.gradeables_for_group[path.parent].append(path.name)

        for path in self.gradeables_for_group:
            if path != self.root:
                self.gradeables_for_group[path.parent].append(path)
        # sort all children of a testgroup lexicographically; this is
        # important for grader settings such as first_error, ignore_sample
        for path in self.gradeables_for_group:
            self.gradeables_for_group[path].sort(key=str)

        self._testdata_settings: dict[Path, dict[str, str]] = (
            {Path(k): v for k, v in settings.items()} if settings is not None else {}
        )

    @lru_cache
    def testdata_settings(self, path: Path):
        """The testdata settings for this path, possibly as implied by ancestors and defaults."""
        parent_settings = (
            self.testdata_settings(path.parent)
            if path != Path()
            else {
                'on_reject': 'break',
                # 'grading': not implemented, so not set
                'grader_flags': '',
                'accept_score': '1',
                'reject_score': '0',
                'range': '-inf inf',
            }
        )
        return parent_settings | (self._testdata_settings.get(path) or {})


class Grades:
    """Grades, typically for a specific submission and set of testcases.

    Initially, no grades are known; when a grade is known (typically when a
    submission is run), set it with 'self.set_verdict(testcase, verdict)'.
    When all testcases are graded (possibly even earlier), self.verdict()
    returns the final verdict.

    Examples
    --------
    >>> g = Grades(['sample/1', 'secret/foo', 'secret/bar'])
    >>> _ = g.set_verdict('1', 'AC')
    >>> _ = g.set_verdict('bar', 'AC')
    >>> g.verdict() is None
    True
    >>> _ = g.set_verdict('foo', 'WA')
    >>> g.verdict()
    'WA'

    You can access the verdicts of testgroups by name
    >>> g.verdict('sample'), g.verdict('secret')
    ('AC', 'WA')
    """

    def __init__(self, testcasepaths, testdata_settings=None):
        """
        Arguments
        ---------

        testcasepaths: a list of full names for all testcases, like ['sample/1', 'secret/foo']

        testdata_settings: maps testgroups (strings) to settings (dicts),
            typically  given in 'testdata.yaml'
        """
        self.testdata = TestData(testcasepaths, testdata_settings)
        self._grade: dict[Path | str, tuple[str, float] | None] = {
            path: None for path in self.testdata.gradeables_for_group
        } | {tcname: None for tcname in self.testdata.cases}

    def set_verdict(
        self, testcase: str, verdict: str, score: float | None = None
    ) -> list[str, tuple[str, float]] | None:
        """
        Set the verdict of this testcase. Returns a list of testgroup grades that
        are the consequens of this verdict.

        Arguments
        ---------
        testcase: the (short) name of a testcase
        verdict: one of 'AC', 'RTE', 'JE', 'TLE', or 'WA'.
        score: a float, optional

        Returns
        -------
        a sequence of tuples of the form

            (testgroup, grade)

        These contain the inferred grades for the testcase and its ancestors, ordered from
        leaf to root. The testgroups are given as strings like 'secret/group1'; the root
        testgroup is called '.'.


        Example
        -------
        >>> g = Grades(['secret/group1/foo'])
        >>> g.set_verdict('foo', 'AC')
        [('secret/group1', ('AC', 1.0)), ('secret', ('AC', 1.0)), ('.', ('AC', 1.0))]
        >>> h = Grades(['sample/1', 'secret/foo', 'secret/bar'])
        >>> h.set_verdict('foo', 'AC')
        []

        A testcase can appear in several testgroups, so the consequences need not form a
        path:
        >>> h = Grades(['secret/foo', 'sample/foo'])
        >>> h.set_verdict('foo', 'AC')
        [('sample', ('AC', 1.0)), ('secret', ('AC', 1.0)), ('.', ('AC', 2.0))]
        """
        if not testcase in self.testdata.cases:
            raise ValueError(f"Use set_grade only for testcases, not {testcase}")
        if self._grade[testcase] is not None and self._grade[testcase] != (verdict, score):
            raise ValueError(f"Grade for {testcase} was already set (to {self._grade[testcase]})")
        self._grade[testcase] = (verdict, score)
        consequences = []
        for path in self.testdata.groups_for_case[testcase]:
            consequences.extend(self.generate_ancestor_grades(path))
        return consequences

    def grade(self, node: str | None = None) -> tuple[str, float] | None:
        """The grade for a testgroup given as a string. If node is None, for the root.

        Returns:
            a tuple (verdict, score), or None if no grade has (yet) been determined.
        """
        if node is None:
            node = "."
        return self._grade[node if node in self.testdata.cases else Path(node)]

    def verdict(self, node: str | None = None) -> str | None:
        """The verdict for a node given as a string. If node is None, for the root.

        Returns None if no grade has (yet) been determined.
        """
        grade = self.grade(node)
        return grade[0] if grade is not None else None

    def score(self, node: str | None = None) -> float | None:
        """The score for a node. If node is None, for the root.

        Returns None if no grade has (yet) been determined.
        """
        grade = self.grade(node)
        return grade[1] if grade is not None else None

    def is_accepted(self, node: str | None = None) -> bool:
        """Does the given node have an accepted verdict? If node is None, for the root."""
        return self.verdict(node) == 'AC'

    def is_rejected(self, node=None) -> bool:
        """Does the given node have a rejected verdict? If node is None, for the root."""
        return self.verdict(node) not in [None, 'AC']

    def generate_ancestor_grades(self, path):
        """For a path of testcase node that just changed its grades[path]
        (from None to a grade), generate the consequences for its ancestors, if any.
        """
        while True:
            children = self.testdata.gradeables_for_group[path]
            settings = self.testdata.testdata_settings(path)
            first_error_idx = min(
                (i for i, c in enumerate(children) if self.is_rejected(c)),
                default=len(children),
            )
            if (
                all(self._grade[c] for c in children)
                or settings['on_reject'] == 'break'
                and all(self.is_accepted(c) for c in children[:first_error_idx])
            ):
                grades = [self.grade(c) for c in children if self.grade(c) is not None]
                grades_with_scores = [
                    (
                        verdict,
                        score
                        if score is not None
                        else settings['accept_score' if verdict == 'AC' else 'reject_score'],
                    )
                    for verdict, score in grades
                ]
                aggregated_grade = aggregate(grades_with_scores, settings=settings)

                if self._grade[path] is None:
                    self._grade[path] = aggregated_grade
                    yield (str(path), aggregated_grade)
                elif self._grade[path] != aggregated_grade:
                    raise ValueError(
                        f"Grade {aggregated_grade} for {path.name} "
                        + f"contradicts {self._grade[path]}"
                    )
            if path == Path():
                break
            path = path.parent

    def __str__(self):
        return self.tree_format()

    def tree_format(self, expectations:Expectations|None=None):
        """Testgroup grades visualised as a tree.

        'Grades.__str__()' uses this for the default string representation.

        >>> grades = Grades(["secret/tiny/foo", "secret/tiny/bar", "secret/large/baz", "sample/1"])
        >>> _ = grades.set_verdict("1", "AC")
        >>> _ = grades.set_verdict("foo", "AC")
        >>> _ = grades.set_verdict("bar", "AC")
        >>> _ = grades.set_verdict("baz", "AC")
        >>> print(grades)
        data      ('AC', 4.0)
        ├─sample  ('AC', 1.0)
        └─secret  ('AC', 3.0)
          ├─large ('AC', 1.0)
          └─tiny  ('AC', 2.0)

        When the grades violate expectations, mention that:

        >>> expectations = Expectations("AC")
        >>> expectations.is_expected('WA')
        False
        >>> grades = Grades(["sample/1", "secret/tc"])
        >>> _ = grades.set_verdict("1", "AC")
        >>> _ = grades.set_verdict("tc", "WA")
        >>> print(grades.tree_format(expectations=expectations))
        data     ('WA', 1.0), expected ({'AC'}, '-inf inf')
        ├─sample ('AC', 1.0)
        └─secret ('WA', 0.0)
        """
        paddinglength = max(
            2 * len(path.parts) + len(path.name)
            for path in self.testdata.gradeables_for_group
            if path not in self.testdata.cases
        )
        return '\n'.join(self._rec(Path(), paddinglength, expectations=expectations))

    def _rec(self, path, paddinglength, expectations=None, prefix='', last=True):
        msg = (
            ""
            if expectations is None or expectations.is_expected(path)
            else f", expected {expectations[path]}"
        )
        branch = '├─' if not last else '└─' if not path == Path() else 'data'
        yield f"{prefix + branch +  path.name:{paddinglength}}" + f" {self.grade(path)}{msg}"
        subgroups = list(
            child
            for child in self.testdata.gradeables_for_group[path]
            if child not in self.testdata.cases
        )
        extension = '│ ' if not last else '  ' if not path == Path() else ''
        for child, is_last in zip(subgroups, [False] * (len(subgroups) - 1) + [True]):
            yield from self._rec(
                child, paddinglength, prefix=prefix + extension, last=is_last
            )


def aggregate(grades, settings):
    """Given a list of grades and settings, determine the default grader's grade."""
    if not grades:
        log('No grades given, so no graders ran')
        return ('AC', 0)

    if settings['on_reject'] == 'break':
        first_rejection = min(
            (i for (i, grade) in enumerate(grades) if grade[0] != "AC"), default=None
        )
        if first_rejection is not None:
            grades = grades[: first_rejection + 1]
    return call_default_grader(grades, grader_flags=settings["grader_flags"])


def call_default_grader(grades, grader_flags=None):
    """Run the default grader to aggregate the given grades;

    grades is a list of tuples
    """

    grader_input = '\n'.join(f"{g[0]} {g[1]}" for g in grades)
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
    return (verdict, float(score))


if __name__ == "__main__":
    import doctest

    doctest.testmod()
