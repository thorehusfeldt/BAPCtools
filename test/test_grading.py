""" Test grading """

import random
from pathlib import Path

import pytest
from grading import call_default_grader, Grades, aggregate, ancestors
from grading import TestData as Data # to avoid confusing pytest about Test...


random.seed(0)

# pylint: disable=no-self-use, missing-function-docstring
class TestDefaultGrader:
    def test_defaults(self):
        # accept if all accept
        assert call_default_grader([("AC", 42), ("AC", 58)]) == ("AC", 100)

        # scoring mode should be `sum`
        assert call_default_grader([("AC", 42), ("WA", 0)]) == ('WA', 42)

        verdicts_by_badness = ["JE", "RTE", "TLE", "WA", "AC"]
        # check all suffixes of verdicts_by_badness
        for i, worst in enumerate(verdicts_by_badness):
            verdicts = verdicts_by_badness[i:]
            random.shuffle(verdicts)
            grader_input = [(v, 0) for v in verdicts]
            assert call_default_grader(grader_input)[0] == worst


class TestAggregate:
    def test_grader_flags(self):
        grades = [("AC", 2), ("AC", 3)]
        flags_and_outcomes = {"min": 2, "max": 3, "sum": 5, "ignore_sample": 3}

        for flag, outcome in flags_and_outcomes.items():
            assert aggregate(grades, {
                "grader_flags": flag,
                "on_reject": "break"
                })[1] == outcome

        grades.append(("WA", 5))
        assert aggregate(grades, {
            "grader_flags": "accept_if_any_accepted",
            "on_reject": "continue",
            }) == ("AC", 10)

        grades.append(("WA", 5))
        assert aggregate(grades, {
            "grader_flags": "accept_if_any_accepted",
            "on_reject": "break",
            }) == ("AC", 10)


GROUPS = ["secret/group1/foo", "secret/group1/bar", "secret/group2/baz", "sample/1"]


def test_ancestors():
    assert ancestors((Path(p) for p in GROUPS)) == set(
        Path(p) for p in [".", "sample", "secret", "secret/group1", "secret/group2"]
    )


def test_DataTree():
    tree = Data(GROUPS)
    assert len(tree.cases) == 4
    assert len(tree.gradeables_for_group) ==  5
    assert Path() in tree.gradeables_for_group
    assert "bar" in tree.gradeables_for_group[Path("secret/group1")]
    assert "bar" not in tree.gradeables_for_group[Path("secret/group2")]
    assert set(tree.gradeables_for_group[tree.root]) == set([Path("secret"), Path("sample")])

# def test_DataTree_iteration():
#     tree = DataTree(GROUPS)
#     assert list(iter(tree)) == ['.', 'sample', 'secret', 'sample/1', 'secret/group1','secret/group2',
#     'secret/group1/bar',
#     'secret/group1/foo',
#     'secret/group2/baz'
 #                              ]



def test_Grades_basics():
    grades = Grades(GROUPS)
    assert grades.grade(grades.testdata.root) is None
    grades.set_verdict("bar", "AC")
    assert grades._grade["bar"] == ("AC", None)
    grades.set_verdict("foo", "AC", score=2)
    assert grades.grade("secret/group1") == ("AC", 3)
    assert grades.grade("secret/group2") is None
    grades.set_verdict("baz", "AC", score=0)
    assert grades.grade("secret") == ("AC", 3)
    assert grades.grade() is None
    grades.set_verdict("1", "AC")
    assert grades.grade(".") == grades.grade() == ("AC", 4)

def test_mixed_subgroups_and_cases():
    grades = Grades(["secret/group1/foo",
                    "secret/group1/bar",
                     "secret/group2/baz",
                     "secret/group2/subgroup/zap",
                     "secret/group2/subgroup/boing",
                     "sample/1"])

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
    assert grades2.testdata.testdata_settings(Path('secret/group1'))['grader_flags'] == 'max accept_if_any_accepted'
    assert grades2.testdata.testdata_settings(Path('secret/group2'))['grader_flags'] == 'sum'
    assert grades2.grade(".") is None
    grades2.set_verdict("bar", "AC", score=5)
    grades2.set_verdict("foo", "WA", score=6)
    grades2.set_verdict("baz", "AC", score=4)
    assert grades2.grade(".") is None
    grades2.set_verdict("1", "AC", score=8)
    assert grades2.grade("secret/group1") == ("AC", 6)
    assert grades2.grade("secret") == ("AC", 10)
    assert grades2.grade(".") == ("AC", 18)

def test_Grades_accept_score_for_testgroup():
    grades3 = Grades(
        GROUPS,
        testdata_settings={
            'secret/group1': {'accept_score': '12'},
            'secret/group2': {'accept_score': '21'},
        },
    )
    grades3.set_verdict("foo", "AC")
    grades3.set_verdict("bar", "AC")
    grades3.set_verdict("baz", "AC")
    grades3.set_verdict("1", "AC")
    assert grades3.grade("secret/group1") == ("AC", 24)
    assert grades3.grade("secret") == ("AC", 45)
    assert grades3.grade(".") == ("AC", 46)


def test_Grades_on_reject_break():
    # check that test group is graded as soon as it can (but not earlier)
    # default is on_reject: break
    grades = Grades(
            ["secret/a", "secret/b", "secret/c", "secret/d"],
            testdata_settings = {'.': {'on_reject': 'break' }} # default, so should be redundant...
            )
    grades.set_verdict("b",  'WA')
    assert grades.verdict() is None # don't know anything, verdicts are '?? WA ?? ??'
    grades.set_verdict("c", 'AC')
    assert grades.verdict() is None # still don't know, verdicts are '?? WA AC ??'
    grades.set_verdict("a", 'AC')
    assert grades.verdict() == 'WA' # verdicts are 'AC WA AC ??', gradeable


def test_Grades_first_error():
    grades = Grades(
            ["secret/1", "secret/2", "secret/3"],
            testdata_settings={ '.': {'on_reject': 'continue', 'grader_flags': 'first_error'}}
            )
    grades.set_verdict("1", "TLE")
    grades.set_verdict("2", "RTE")
    grades.set_verdict("3", "WA")
    assert grades.verdict() == "TLE"

def test_Grades_worst_error():
    grades = Grades(
            ["secret/1", "secret/2", "secret/3"],
            testdata_settings={ '.': {'on_reject': 'continue'}} # worst_error is default
            )
    grades.set_verdict("1", "TLE")
    grades.set_verdict("2", "RTE")
    grades.set_verdict("3", "WA")
    assert grades.verdict() == "RTE"

def test_recursive_inheritance_of_testdata_settings():
    grades = Grades(
        GROUPS,
        testdata_settings={ '.': {'accept_score': '2'}}
    )
    grades.set_verdict("foo", "AC")
    grades.set_verdict("bar", "AC", score=1)
    grades.set_verdict("baz", "AC")
    grades.set_verdict("1", "AC")
    assert grades.grade() == ('AC', 7)

def test_different_testdata_settings_for_same_testcase():
    grades = Grades(
        ['sample/foo', 'secret/foo'],
        testdata_settings={'sample': {'accept_score': '2'},
                           'secret': {'accept_score': '3'}}
    )
    grades.set_verdict("foo", "AC")
    assert grades.grade('sample') == ('AC', 2)
    assert grades.grade('secret') == ('AC', 3)
    assert grades.grade() == ('AC', 5)


def test_prettyprint(capsys):
    grades = Grades(["secret/group1/foo",
                    "secret/group1/bar",
                     "secret/group2/baz",
                     "secret/group2/subgroup/zap",
                     "secret/group2/subgroup/boing",
                     "sample/1"]
)
    grades.set_verdict("1", "AC")
    grades.set_verdict("foo", "AC")
    grades.set_verdict("bar", "AC")
    grades.set_verdict("baz", "AC")
    grades.set_verdict("zap", "AC")
    grades.set_verdict("boing", "AC")
    assert str(grades) == """data           ('AC', 6.0)
├─sample       ('AC', 1.0)
└─secret       ('AC', 5.0)
  ├─group1     ('AC', 2.0)
  └─group2     ('AC', 3.0)
    └─subgroup ('AC', 2.0)"""
