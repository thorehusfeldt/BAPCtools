""" Methods for dealing with test groups and grades.

    Terminology used here:

    - verdict: 'ACCEPTED', 'WRONG_ANSWER', etc. (in its long form)
    - score: a number
    - grade: a tuple of (verdict, score)
    - (test case) result: a util.ExecResult, it has result.verdict

    - testdata tree: the tree given by the full filenames in data
    - testdata group: an *internal* node in the test data tree (spec is unclear about this)
    - testcase: a leaf of the test data tree

    The verdict of the grade at the root of the testdata tree is the final verdict of the
    default grader on all the testdata.
"""

import re
import subprocess
from pathlib import PurePath

from util import log, error, debug
import config


class Grades:
    """The grades for all testcases and testgroups of a submission.
    This forms a tree defined by self.children[node], leaves are testcases.
    Tree nodes are identified by pathlib.PurePath objects,
    the root is self.root == PurePath('.') whose children (if they exist) are
    PurePath('sample') and PurePath('secret')

    self.grade[node] is the grade determined by the default grader for a node in the testdata tree.
    self.verdict = the final verdict at the root
    """

    def __init__(self, tcresults):
        """tcresults is a dict of util.ExecResult objects indexed by testcase name"""
        self.root = PurePath('.')

        # self.grade for the leaves is just the verdict in ExecResult,
        # We hard-code score is 1 for AC, 0 for everything else
        self.grade = {
            PurePath(tc): (result.verdict, int(result.verdict == 'ACCEPTED'))
            for tc, result in tcresults.items()
        }

        # Build tree structure of testcases and test(sub)groups
        self.testcases = set(self.grade.keys())
        self.children = {node: [] for node in set(p for tc in self.testcases for p in tc.parents)}
        for node in self.testcases | self.children.keys():
            if node != self.root:
                self.children[node.parent].append(node)

        # compute the grade for each internal node recursively from the root
        self.grade[self.root] = self._grade_recursively(self.root)

    def _grade_recursively(self, node):
        if node not in self.grade:
            grades = [self._grade_recursively(c) for c in self.children[node]]
            self.grade[node] = aggregate(node, grades)
        return self.grade[node]

    def verdict(self):
        """The final verdict for all testcases (including samples)"""
        return self.grade[self.root][0]

    def _rec_prettyprint_tree(self, node, paddinglength, depth, prefix: str = ''):
        if depth <= 0:
            return
        subgroups = list(
            sorted(child for child in self.children[node] if child not in self.testcases)
        )
        branches = ['├─ '] * (len(subgroups) - 1) + ['└─ ']
        for branch, child in zip(branches, subgroups):
            if child not in self.testcases:
                print(f"{prefix + branch + child.name:{paddinglength}} {self.grade[child][0]}")
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
            for node in self.children
            if node not in self.testcases and len(node.parts) <= maxdepth
        )
        self._rec_prettyprint_tree(self.root, paddinglength, maxdepth)


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

    short_verdict = {
        'ACCEPTED': 'AC',
        'WRONG_ANSWER': 'WA',
        'JUDGE_ERROR': 'JE',
        'TIME_LIMIT_EXCEEDED': 'TLE',
        'RUN_TIME_ERROR': 'RTE',
    }
    long_verdict = {v: k for k, v in short_verdict.items()}

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
