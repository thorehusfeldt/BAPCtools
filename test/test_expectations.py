""" Test grading """

import random
from pathlib import Path

import pytest
from expectations import Expectations

random.seed(0)

GROUPS = ["secret/group1/foo", "secret/group1/bar", "secret/group2/baz", "sample/1"]
ALL_VERDICTS = set(["AC", "TLE", "WA", "RTE"])

# pylint: disable=no-self-use, missing-function-docstring


def test_set_expectations_four_different_ways():
    e = Expectations(
        expectations={
            'secret': {'1': 'AC', '2': ['AC'], '3': {'verdict': 'AC'}, '4': {'verdict': ['AC']}}
        }
    )
    assert e.verdicts("secret/1") == set(["AC"])
    assert e.verdicts("secret/2") == set(["AC"])
    assert e.verdicts("secret/3") == set(["AC"])
    assert e.verdicts("secret/4") == set(["AC"])


def test_set_expected_results():
    e = Expectations(expected_results=["CORRECT"])
    assert e.verdicts() == set(["AC"])
    e = Expectations(expected_results=["CORRECT", "WRONG-ANSWER"])
    assert e.verdicts() != set(["AC"])


def test_set_from_dirname():
    e = Expectations(dirname="accepted")
    assert e.verdicts() == set(["AC"])
    e = Expectations(dirname="partially_accepted")
    assert e.verdicts() != set(["AC"])


def test_Expectations_accept_inherited_downwards():
    # First see that AC from the root gets passed down
    e = Expectations(expectations="AC")
    assert e.verdicts() == set(["AC"])
    assert e.verdicts("secret") == set(["AC"])
    assert e.verdicts("secret/group1/foo") == set(["AC"])


def test_Expectations_with_testgroups():
    # Richer example of expecations
    e = Expectations(
        expectations={'verdict': ['WA', 'TLE'], 'sample': 'AC', 'secret': {'group1': ['AC']}}
    )
    assert e.verdicts() == set(["WA", "TLE"])
    assert e.verdicts("sample") == set(["AC"])
    assert e.verdicts("secret/group1") == set(["AC"])
    assert e.verdicts("secret/group1/foo") == set(["AC"])
    assert "TLE" in e.verdicts("secret/group2/baz")


def test_Expectations_one_testgroup():
    # Very simple example of expecations
    e = Expectations(expectations={'secret': {'group1': 'AC'}})
    assert e.verdicts("secret/group1") == set(["AC"])
    assert e.verdicts("secret/group1/subgroup") == set(["AC"])
    assert e.verdicts("secret/group1/subgroup/sometask") == set(["AC"])
    assert e.verdicts("secret/group2") == ALL_VERDICTS  # know nothing about 'secret'


def test_Expectations_ignore_sample():
    exp = Expectations(
        expectations="AC", testdata_settings={'.': {'grader_flags': 'ignore_sample'}}
    )
    assert exp.verdicts() == exp.verdicts('secret') == set(["AC"])
    assert exp.verdicts('sample') == ALL_VERDICTS
    exp = Expectations(expectations="AC")
    assert exp.verdicts() == exp.verdicts('secret') == exp.verdicts('sample') == set(["AC"])
    exp = Expectations(expectations="AC", testdata_settings={'.': {'grader_flags': ''}})
    assert exp.verdicts() == exp.verdicts('secret') == exp.verdicts('sample') == set(["AC"])


def test_Expectations_any_accepted():
    exp = Expectations(
        expectations="AC", testdata_settings={'.': {'grader_flags': 'accept_if_any_accepted'}}
    )
    assert exp.verdicts('sample') == exp.verdicts('secret') == ALL_VERDICTS


def test_Expectations_always_accept():
    exp = Expectations(
        expectations="AC", testdata_settings={'.': {'grader_flags': 'always_accept'}}
    )
    assert exp.verdicts('sample') == exp.verdicts('secret') == ALL_VERDICTS

def test_Expectations_various_getters():
    exp = Expectations(expectations=["AC"])
    assert exp[""] == exp['sample'] == (set(["AC"]), "-inf inf")
    assert exp.verdicts() == exp.verdicts("") == exp.verdicts(".") == exp.verdicts('sample') == set(["AC"])
    assert exp.range() == exp.range("") == exp.range(".") == exp.range('sample') == "-inf inf"
    assert exp.is_expected("AC")
    assert exp.is_expected(("AC", float("-inf")))
    assert exp.is_expected(("AC", float("inf")))
    assert exp.is_expected(("AC", float("+inf")))
    assert exp.is_expected(("AC", 42))
    assert exp.is_expected(("AC", -42.85))
    assert not exp.is_expected(("WA"))

def test_Expectations_range():
    exp = Expectations(expectations={'verdict': 'AC', 'score': '0 23'})
    assert exp[""] == (set(["AC"]), "0 23")
    assert exp.is_expected(("AC", 0))
    assert exp.is_expected(("AC", 23))
    assert exp.is_expected(("AC", 11))
    assert exp.is_expected(("AC", .05))
    assert not exp.is_expected(("AC", -1))
    assert not exp.is_expected(("AC", 24))
    assert not exp.is_expected(("WA", 10))

def test_Expectations_exceptions():
    Expectations(expectations="AC", expected_results=["CORRECT"])
    Expectations(expectations="AC", dirname="accepted")
    Expectations(expectations="WA", expected_results=["WRONG-ANSWER"], dirname="mixed")
    with pytest.raises(ValueError):
        Expectations(expectations="AC", dirname="wrong_answer")
    with pytest.raises(ValueError):
        Expectations(expectations="AC", expected_results=["WRONG-ANSWER"])
    with pytest.raises(ValueError):
        Expectations(expected_results=["CORRECT"], dirname='accepted')
