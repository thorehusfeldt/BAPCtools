""" Methods for dealing with test groups and grades.

    Terminology used here:

    - verdict: 'ACCEPTED', 'WRONG_ANSWER', etc. (in its long form)
    - score: a number
    - grade: a tuple of (verdict, score)
    - (test case) result: a util.ExecResult, it has result.verdict

    - testdatatree: the tree given by the full filenames in data
    - testgroup: an *internal* node in the test data tree (spec is unclear about this)
    - testcase: a leaf of the test data tree

    The verdict of the grade at the root of the testdatatree is the final verdict of the
    default grader on all the testdata.
"""

import re
import subprocess
from pathlib import PurePath

from util import log, warn, error, debug
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

# pylint: disable=too-few-public-methods
class TestDataTree:
    """The tree for all testcases and testgroups of a problem (in fact, the run or a problem).
    This forms a tree defined by self.children[node], leaves are testcases.
    Tree nodes are identified by pathlib.PurePath objects,
    the root is self.root == PurePath('.') whose children (if they exist) are
    PurePath('sample') and PurePath('secret')
    """

    def __init__(self, testcasepaths):
        """testcases is an iterable of pathlib.Paths"""

        self.root = PurePath('.')

        # Build tree structure of testcases and test(sub)groups
        self.leaves = set(testcasepaths)
        self.children = {node: [] for node in set(p for tc in self.leaves for p in tc.parents)}
        self.nodes = self.leaves | set(self.children.keys())
        for node in self.nodes:
            if node != self.root:
                self.children[node.parent].append(node)


class Grades:
    """The grades for all testcases and testgroups of a list of test results
    This forms a tree defined by self.children[node], leaves are testcases.
    Tree nodes are identified by pathlib.PurePath objects,
    the root is self.root == PurePath('.') whose children (if they exist) are
    PurePath('sample') and PurePath('secret')

    self.grade[node] is the grade determined by the default grader for a node in the testdata tree.
    self.verdict = the final verdict at the root
    self.expectations[node] is None or a list of verdicts, such as ["AC"]
    """

    def __init__(self, tcresults):
        """tcresults is a dict of util.ExecResult objects indexed by testcase name"""

        self.tree: TestDataTree = TestDataTree(PurePath(tc) for tc in tcresults)

        # self.grade for the leaves is just the verdict in ExecResult,
        # We hard-code score is 1 for AC, 0 for everything else
        self.grades = {
            PurePath(tc): (result.verdict, int(result.verdict == 'ACCEPTED'))
            for tc, result in tcresults.items()
        }

        # compute the grade for each internal node recursively from the root
        self.grades[self.tree.root] = self._grade_recursively(self.tree.root)
        self.expectations = None

    def _grade_recursively(self, node):
        if node not in self.grades:
            grades = [self._grade_recursively(c) for c in self.tree.children[node]]
            self.grades[node] = aggregate(node, grades)
        return self.grades[node]

    def verdict(self):
        """The final verdict for all testcases (including samples)"""
        return self.grades[self.tree.root][0]

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
                if self.expectations is not None:
                    expectations = self.expectations.get(child)
                    if expectations is not None:
                        color = Fore.GREEN if short_verdict[grade] in expectations else Fore.RED
                    else:
                        color = Fore.YELLOW
                else:
                    color = Fore.YELLOW
                print(
                    f"{prefix + branch + child.name:{paddinglength}}",
                    f"{color}{self.grades[child][0]}{Style.RESET_ALL}",
                )
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

    def set_expectations(self, expected_grades):
        """Populate self.expectations[p] for every node p in the testdatatree.
        expected_grades is a string (for the root) or a dict indexed by strings, typically
        expected_grades_yaml[submission.short_path]
        """
        self.expectations = {}
        if expected_grades is None:
            return
        self._set_expectations_rec(expected_grades, self.tree.root)

    def _set_expectations_rec(self, expected_grades, node: PurePath):
        if isinstance(expected_grades, dict):
            expected_verdicts = expected_grades.get('verdict') # could be None
            if 'subgroups' in expected_grades:
                for testgroup in expected_grades['subgroups']:  # 'sample', 'secret', 'edgecases', ...
                    if not node / testgroup in self.tree.nodes:
                        warn(
                            f"Found expected grades for {node / testgroup}, but no such testgroup has testcases"
                        )
                    self._set_expectations_rec(expected_grades['subgroups'][testgroup], node / testgroup)
        else: # str or list
            expected_verdicts = expected_grades
        # make sure it's a list (possibly of a singleton), unless it's None
        if isinstance(expected_verdicts, str):
            self.expectations[node] = [expected_verdicts]


def aggregate(path, grades):
    """Given a list of grades, determine the default grader's grade per testgroup."""
    if not grades:
        log(f'No results on {path}, so no graders ran')
        return ('ACCEPTED', 0)

    verdict, score = call_default_grader(grades)
    return verdict, score


def call_default_grader(grades):
    """Run the default grader to aggregate grades;
    this involves translating from 'ACCEPTED' to 'AC' and back.

    Doesn't understand grader flags.
    Doesn't understand testdata.yaml.
    """

    grader_input = '\n'.join(f"{short_verdict[v]} {s}" for v, s in grades)

    grader = subprocess.Popen(
        config.tools_root / 'support' / 'default_grader.py',
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
