""" Test grading """

import random
from pathlib import Path

import pytest
import grading


random.seed(0)

# pylint: disable=no-self-use, missing-function-docstring
class TestDefaultGrader:
    def test_defaults(self):
        # accept if all accept
        verdict, score = grading.call_default_grader([("AC", 42), ("AC", 58)])
        assert verdict == "AC" and score == 100

        # scoring mode should be `sum`
        verdict, score = grading.call_default_grader([("AC", 42), ("WA", 0)])
        assert verdict == "WA" and score == 42

        verdicts_by_badness = ["JE", "RTE", "TLE", "WA", "AC"]
        # check all suffixes of verdicts_by_badness
        for i, worst in enumerate(verdicts_by_badness):
            verdicts = verdicts_by_badness[i:]
            random.shuffle(verdicts)
            grader_input = [(v, 0) for v in verdicts]
            verdict, _ = grading.call_default_grader(grader_input)
            assert verdict == worst


class TestAggregate:
    def test_grader_flags(self):
        grades = [("AC", 2), ("AC", 3)]
        flags_and_outcomes = {"min": 2, "max": 3, "sum": 5, "ignore_sample": 3}

        for flag, outcome in flags_and_outcomes.items():
            assert grading.aggregate(None, grades, {
                "grader_flags": flag,
                "on_reject": "break"
                })[1] == outcome

        grades.append(("WA", 5))
        assert grading.aggregate(None, grades, {
            "grader_flags": "accept_if_any_accepted",
            "on_reject": "continue",
            }) == (
            "AC",
            10,
        )

        grades.append(("WA", 5))
        assert grading.aggregate(None, grades, {
            "grader_flags": "accept_if_any_accepted",
            "on_reject": "break",
            }) == (
            "AC",
            10,
        )


GROUPS = ["secret/group1/foo", "secret/group1/bar", "secret/group2/baz", "sample/1"]


def test_ancestors():
    assert grading.ancestors(GROUPS) == set(
        [".", "sample", "secret", "secret/group1", "secret/group2"]
    )


def test_TestDataTree():
    tree = grading.TestDataTree(GROUPS)
    assert len(tree.nodes) == 9
    assert "." in tree.nodes
    assert "secret/group1/bar" in tree.children["secret/group1"]
    assert "secret/group1/bar" not in tree.children["secret/group2"]
    assert set(tree.children[tree.root]) == set(["secret", "sample"])

def test_TestDataTree_iteration():
    tree = grading.TestDataTree(GROUPS)
    assert list(iter(tree)) == ['.', 'sample', 'secret', 'sample/1', 'secret/group1','secret/group2',
    'secret/group1/bar',
    'secret/group1/foo',
    'secret/group2/baz'
                               ]



def test_Grades_basics():
    grades = grading.Grades(GROUPS)
    assert grades.grades[grades.tree.root] is None
    grades["secret/group1/bar"] = ("AC", 1)
    assert grades["secret/group1/bar"] == ("AC", 1)
    grades["secret/group1/foo"] = ("AC", 1)
    assert grades["secret/group1"] == ("AC", 2)
    assert grades["secret/group2"] is None
    grades["secret/group2/baz"] = ("AC", 1)
    assert grades["secret"] == ("AC", 3)
    assert grades["."] is None
    grades["sample/1"] = ("AC", 1)
    assert grades["."] == ("AC", 4)


def test_Grades_grader_flags():
    # Now pass some grader flags using testdata_settings
    grades2 = grading.Grades(
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
    grades2["secret/group1/bar"] = ("AC", 5)
    grades2["secret/group1/foo"] = ("WA", 6)
    grades2["secret/group2/baz"] = ("AC", 4)
    assert grades2["."] is None
    grades2["sample/1"] = ("AC", 8)
    assert grades2["secret/group1"] == ("AC", 6)
    assert grades2["secret"] == ("AC", 10)
    assert grades2["."] == ("AC", 18)

def test_Grades_accept_score_for_testgroup():
    grades3 = grading.Grades(
        GROUPS,
        testdata_settings={
            'secret/group1': {'accept_score': '12'},
            'secret/group2': {'accept_score': '21'},
        },
    )
    grades3["secret/group1/foo"] = ("AC")
    grades3["secret/group1/bar"] = ("AC")
    grades3["secret/group2/baz"] = ("AC")
    grades3["sample/1"] = ("AC")
    assert grades3["secret/group1"] == ("AC", 24)
    assert grades3["secret"] == ("AC", 45)
    assert grades3["."] == ("AC", 46)


def test_set_excpecations_four_different_ways():
    grades = grading.Grades(
            ["secret/1", "secret/2", "secret/3", "secret/4"],
            expectations= {
                'secret': {
                    '1': 'AC',
                    '2': ['AC'],
                    '3': { 'verdict': 'AC' },
                    '4': { 'verdict': ['AC'] }
                    }})
    assert grades.expectations["secret/1"].verdicts == set(["AC"])
    assert grades.expectations["secret/2"].verdicts == set(["AC"])
    assert grades.expectations["secret/3"].verdicts == set(["AC"])
    assert grades.expectations["secret/4"].verdicts == set(["AC"])

def test_Expectations_accept_inherited_downwards():
    # First see that AC from the root gets passed down
    grades4 = grading.Grades(
            GROUPS,
            expectations = "AC"
            )
    assert grades4.expectations["."].verdicts == set(["AC"])
    assert grades4.expectations["secret"].verdicts == set(["AC"])
    assert grades4.expectations["secret/group1/foo"].verdicts == set(["AC"])

def test_Expectations_with_testgroups():
    # Richer example of expecations
    grades5 = grading.Grades(
            GROUPS,
            expectations = {
                'verdict': ['WA', 'TLE'],
                'sample': 'AC',
                'secret': {
                    'group1': ['AC']
                    }
                }
            )
    assert grades5.expectations["."].verdicts == set(["WA", "TLE"])
    assert grades5.expectations["sample"].verdicts == set(["AC"])
    assert grades5.expectations["secret/group1"].verdicts == set(["AC"])
    assert grades5.expectations["secret/group1/foo"].verdicts == set(["AC"])
    assert "TLE" in grades5.expectations["secret/group2/baz"].verdicts

def test_Expectations_one_testgroup():
    # Very simple example of expecations
    grades = grading.Grades(
            GROUPS,
            expectations = { 'secret': { 'group1': 'AC' } }
            )
    assert grades.expectations["secret/group1"].verdicts == set(["AC"])
    assert "TLE" in grades.expectations["secret/group2"].verdicts

def test_Grades_on_reject_break():
    # check that test group is graded as soon as it can (but not earlier)
    # default is on_reject: break
    grades = grading.Grades(
            ["secret/a", "secret/b", "secret/c", "secret/d"],
            testdata_settings = {'.': {'on_reject': 'break' }} # default, so should be redundant...
            )
    grades["secret/b"] = 'WA'
    assert grades.verdict() is None # don't know anything, verdicts are '?? WA ?? ??'
    grades["secret/c"] = 'AC'
    assert grades.verdict() is None # still don't know, verdicts are '?? WA AC ??'
    grades["secret/a"] = 'AC'
    assert grades.verdict() == 'WA' # verdicts are 'AC WA AC ??', gradeable


def test_Grades_first_error():
    grades = grading.Grades(
            ["secret/1", "secret/2", "secret/3"],
            testdata_settings={ '.': {'on_reject': 'continue', 'grader_flags': 'first_error'}}
            )
    grades["secret/1"] = ("TLE", 1)
    grades["secret/2"] = ("RTE", 1)
    grades["secret/3"] = ("WA", 1)
    assert grades.verdict() == "TLE"

def test_Grades_worst_error():
    grades = grading.Grades(
            ["secret/1", "secret/2", "secret/3"],
            testdata_settings={ '.': {'on_reject': 'continue'}} # worst_error is default
            )
    grades["secret/1"] = ("TLE", 1)
    grades["secret/2"] = ("RTE", 1)
    grades["secret/3"] = ("WA", 1)
    assert grades.verdict() == "RTE"

def test_recursive_inheritance_of_testdata_settings():
    grades = grading.Grades(
        GROUPS,
        testdata_settings={ '.': {'accept_score': '2'}}
    )
    grades["secret/group1/foo"] = "AC"
    grades["secret/group1/bar"] = "AC"
    grades["secret/group2/baz"] = "AC"
