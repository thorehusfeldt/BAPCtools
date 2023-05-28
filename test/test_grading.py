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
        verdict, score = grading.call_default_grader([("ACCEPTED", 42), ("ACCEPTED", 58)])
        assert verdict == "ACCEPTED" and score == 100

        # scoring mode should be `sum`
        verdict, score = grading.call_default_grader([("ACCEPTED", 42), ("WRONG_ANSWER", 0)])
        assert verdict == "WRONG_ANSWER" and score == 42

        verdicts_by_badness = [
            "JUDGE_ERROR",
            "RUN_TIME_ERROR",
            "TIME_LIMIT_EXCEEDED",
            "WRONG_ANSWER",
            "ACCEPTED",
        ]
        # check all suffixes of verdicts_by_badness
        for i, worst in enumerate(verdicts_by_badness):
            verdicts = verdicts_by_badness[i:]
            random.shuffle(verdicts)
            grader_input = [(v, 0) for v in verdicts]
            verdict, _ = grading.call_default_grader(grader_input)
            assert verdict == worst


class TestAggregate:
    def test_grader_flags(self):
        grades = [("ACCEPTED", 2), ("ACCEPTED", 3)]
        flags_and_outcomes = {"min": 2, "max": 3, "sum": 5, "ignore_sample": 3}

        for flag, outcome in flags_and_outcomes.items():
            assert grading.aggregate(None, grades, {"grader_flags": flag})[1] == outcome

        grades.append(("WRONG_ANSWER", 5))
        assert grading.aggregate(None, grades, {"grader_flags": "accept_if_any_accepted"}) == (
            "ACCEPTED",
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
    grades["secret/group1/bar"] = ("ACCEPTED", 1)
    assert grades["secret/group1/bar"] == ("ACCEPTED", 1)
    grades["secret/group1/foo"] = ("ACCEPTED", 1)
    assert grades["secret/group1"] == ("ACCEPTED", 2)
    assert grades["secret/group2"] is None
    grades["secret/group2/baz"] = ("ACCEPTED", 1)
    assert grades["secret"] == ("ACCEPTED", 3)
    assert grades["."] is None
    grades["sample/1"] = ("ACCEPTED", 1)
    assert grades["."] == ("ACCEPTED", 4)


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
    grades2["secret/group1/foo"] = ("ACCEPTED", 5)
    grades2["secret/group1/bar"] = ("WRONG_ANSWER", 6)
    grades2["secret/group2/baz"] = ("ACCEPTED", 4)
    assert grades2["."] is None
    grades2["sample/1"] = ("ACCEPTED", 8)
    assert grades2["secret/group1"] == ("ACCEPTED", 6)
    assert grades2["secret"] == ("ACCEPTED", 10)
    assert grades2["."] == ("ACCEPTED", 18)

def test_Grades_accept_score_for_testgroup():
    grades3 = grading.Grades(
        GROUPS,
        testdata_settings={
            'secret/group1': {'accept_score': '12'},
            'secret/group2': {'accept_score': '21'},
        },
    )
    grades3["secret/group1/foo"] = ("ACCEPTED")
    grades3["secret/group1/bar"] = ("ACCEPTED")
    grades3["secret/group2/baz"] = ("ACCEPTED")
    grades3["sample/1"] = ("ACCEPTED")
    assert grades3["secret/group1"] == ("ACCEPTED", 24)
    assert grades3["secret"] == ("ACCEPTED", 45)
    assert grades3["."] == ("ACCEPTED", 46)


def test_Expectations_accept_inherited_downwards():
    # First see that ACCEPTED from the root gets passed down
    grades4 = grading.Grades(
            GROUPS,
            expectations = "ACCEPTED"
            )
    assert grades4.expectations["."].verdicts == set(["ACCEPTED"])
    assert grades4.expectations["secret"].verdicts == set(["ACCEPTED"])
    assert grades4.expectations["secret/group1/foo"].verdicts == set(["ACCEPTED"])

def test_Expectations_with_testgroups():
    # Richer example of expecations
    grades5 = grading.Grades(
            GROUPS,
            expectations = {
                'verdict': ['WRONG_ANSWER', 'TIME_LIMIT_EXCEEDED'],
                'sample': 'ACCEPTED',
                'secret': {
                    'group1': ['ACCEPTED']
                    }
                }
            )
    assert grades5.expectations["."].verdicts == set(["WRONG_ANSWER", "TIME_LIMIT_EXCEEDED"])
    assert grades5.expectations["sample"].verdicts == set(["ACCEPTED"])
    assert grades5.expectations["secret/group1"].verdicts == set(["ACCEPTED"])
    assert grades5.expectations["secret/group1/foo"].verdicts == set(["ACCEPTED"])
    assert "TIME_LIMIT_EXCEEDED" in grades5.expectations["secret/group2/baz"].verdicts

def test_Grades_first_error():
    grades = grading.Grades(GROUPS)
    grades["secret/group1/foo"] = ("TIME_LIMIT_EXCEEDED", 1)
    grades["secret/group1/bar"] = ("WRONG_ANSWER", 1)
    grades["secret/group2/baz"] = ("RUN_TIME_ERROR", 1)
    assert grades.verdict("secret/group1") == "TIME_LIMIT_EXCEEDED"
    assert grades.verdict("secret") == "RUN_TIME_ERROR"

def test_recursive_inheritance_of_testdata_settings():
    grades = grading.Grades(
        GROUPS,
        testdata_settings={ '.': {'accept_score': '2'}}
    )
    grades["secret/group1/foo"] = "ACCEPTED"
    grades["secret/group1/bar"] = "ACCEPTED"
    grades["secret/group2/baz"] = "ACCEPTED"
    grades["sample/1"] = "ACCEPTED"
    assert grades.score() == 8
