""" Test grading """

import random
from pathlib import Path

import pytest
from grading import Grade, call_default_grader, Grades, aggregate, ancestors
from grading import TestDataTree as DataTree # to avoid confusing pytest about Test...


random.seed(0)

# pylint: disable=no-self-use, missing-function-docstring
class TestDefaultGrader:
    def test_defaults(self):
        # accept if all accept
        assert call_default_grader([Grade("AC", 42), Grade("AC", 58)]) == Grade("AC", 100)

        # scoring mode should be `sum`
        assert call_default_grader([Grade("AC", 42), Grade("WA", 0)]) == Grade('WA', 42)

        verdicts_by_badness = ["JE", "RTE", "TLE", "WA", "AC"]
        # check all suffixes of verdicts_by_badness
        for i, worst in enumerate(verdicts_by_badness):
            verdicts = verdicts_by_badness[i:]
            random.shuffle(verdicts)
            grader_input = [Grade(v, 0) for v in verdicts]
            assert call_default_grader(grader_input).verdict == worst


class TestAggregate:
    def test_grader_flags(self):
        grades = [Grade("AC", 2), Grade("AC", 3)]
        flags_and_outcomes = {"min": 2, "max": 3, "sum": 5, "ignore_sample": 3}

        for flag, outcome in flags_and_outcomes.items():
            assert aggregate(None, grades, {
                "grader_flags": flag,
                "on_reject": "break"
                }).score == outcome

        grades.append(Grade("WA", 5))
        assert aggregate(None, grades, {
            "grader_flags": "accept_if_any_accepted",
            "on_reject": "continue",
            }) == Grade("AC", 10)

        grades.append(Grade("WA", 5))
        assert aggregate(None, grades, {
            "grader_flags": "accept_if_any_accepted",
            "on_reject": "break",
            }) == Grade("AC", 10)


GROUPS = ["secret/group1/foo", "secret/group1/bar", "secret/group2/baz", "sample/1"]


def test_ancestors():
    assert ancestors(GROUPS) == set(
        [".", "sample", "secret", "secret/group1", "secret/group2"]
    )


def test_DataTree():
    tree = DataTree(GROUPS)
    assert len(tree.nodes) == 9
    assert "." in tree.nodes
    assert "secret/group1/bar" in tree.children["secret/group1"]
    assert "secret/group1/bar" not in tree.children["secret/group2"]
    assert set(tree.children[tree.root]) == set(["secret", "sample"])

def test_DataTree_iteration():
    tree = DataTree(GROUPS)
    assert list(iter(tree)) == ['.', 'sample', 'secret', 'sample/1', 'secret/group1','secret/group2',
    'secret/group1/bar',
    'secret/group1/foo',
    'secret/group2/baz'
                               ]



def test_Grades_basics():
    grades = Grades(GROUPS)
    assert grades[grades.tree.root] is None
    grades.set_grade("secret/group1/bar", "AC", 1)
    assert grades["secret/group1/bar"] == Grade("AC", 1)
    grades.set_grade("secret/group1/foo", "AC", 1)
    assert grades["secret/group1"] == Grade("AC", 2)
    assert grades["secret/group2"] is None
    grades.set_grade("secret/group2/baz", "AC", 1)
    assert grades["secret"] == Grade("AC", 3)
    assert grades["."] is None
    grades.set_grade("sample/1", "AC", 1)
    assert grades["."] == Grade("AC", 4)


def test_Grades_grader_flags():
    # Now pass some grader flags using testdata_settings
    grades2 = Grades(
        GROUPS,
        testdata_settings={
            'secret/group1': {'grader_flags': 'max accept_if_any_accepted'},
            'secret': {'grader_flags': 'sum'},
            '.': {'grader_flags': 'sum'},
        },
    )
    assert grades2.tree.settings['secret/group1']['grader_flags'] == 'max accept_if_any_accepted'
    assert grades2.tree.settings['secret/group2']['grader_flags'] == 'sum'
    assert grades2["."] is None
    grades2.set_grade("secret/group1/bar", "AC", 5)
    grades2.set_grade("secret/group1/foo", "WA", 6)
    grades2.set_grade("secret/group2/baz", "AC", 4)
    assert grades2["."] is None
    grades2.set_grade("sample/1", "AC", 8)
    assert grades2["secret/group1"] == Grade("AC", 6)
    assert grades2["secret"] == Grade("AC", 10)
    assert grades2["."] == Grade("AC", 18)

def test_Grades_accept_score_for_testgroup():
    grades3 = Grades(
        GROUPS,
        testdata_settings={
            'secret/group1': {'accept_score': '12'},
            'secret/group2': {'accept_score': '21'},
        },
    )
    grades3.set_grade("secret/group1/foo", "AC")
    grades3.set_grade("secret/group1/bar", "AC")
    grades3.set_grade("secret/group2/baz", "AC")
    grades3.set_grade("sample/1", "AC")
    assert grades3["secret/group1"] == Grade("AC", 24)
    assert grades3["secret"] == Grade("AC", 45)
    assert grades3["."] == Grade("AC", 46)




def test_Grades_on_reject_break():
    # check that test group is graded as soon as it can (but not earlier)
    # default is on_reject: break
    grades = Grades(
            ["secret/a", "secret/b", "secret/c", "secret/d"],
            testdata_settings = {'.': {'on_reject': 'break' }} # default, so should be redundant...
            )
    grades.set_grade("secret/b",  'WA')
    assert grades.verdict() is None # don't know anything, verdicts are '?? WA ?? ??'
    grades.set_grade("secret/c", 'AC')
    assert grades.verdict() is None # still don't know, verdicts are '?? WA AC ??'
    grades.set_grade("secret/a", 'AC')
    assert grades.verdict() == 'WA' # verdicts are 'AC WA AC ??', gradeable


def test_Grades_first_error():
    grades = Grades(
            ["secret/1", "secret/2", "secret/3"],
            testdata_settings={ '.': {'on_reject': 'continue', 'grader_flags': 'first_error'}}
            )
    grades.set_grade("secret/1", "TLE")
    grades.set_grade("secret/2", "RTE")
    grades.set_grade("secret/3", "WA")
    assert grades.verdict() == "TLE"

def test_Grades_worst_error():
    grades = Grades(
            ["secret/1", "secret/2", "secret/3"],
            testdata_settings={ '.': {'on_reject': 'continue'}} # worst_error is default
            )
    grades.set_grade("secret/1", "TLE")
    grades.set_grade("secret/2", "RTE")
    grades.set_grade("secret/3", "WA")
    assert grades.verdict() == "RTE"

def test_recursive_inheritance_of_testdata_settings():
    grades = Grades(
        GROUPS,
        testdata_settings={ '.': {'accept_score': '2'}}
    )
    grades.set_grade("secret/group1/foo", "AC")
    grades.set_grade("secret/group1/bar", "AC")
    grades.set_grade("secret/group2/baz", "AC")
