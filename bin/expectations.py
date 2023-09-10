"""Expectations for a submission

Here is a sample expectations.yaml file:

    accepted/: accepted     # Every submission in accepted/* should be accepted
    wrong_answer/th.py:     # This particular submission ...
      sample: accepted      # ... should be acceped on sample
      secret: wrong answer  # ... but fail with WA on some test case in secret
    mixed/failing.java      # For this particular submission, ...
      secret/huge/graph07:  # ... on this particular test case ...
        allowed: [TLE, RTE] # ... only TLE and RTE are allowed

A yaml parser will turn this into a dict that can be fed to the Registry class:

>>> exp_dict = {
...     "accepted/": "accepted", 
...     "wrong_answer/th.py": {"sample": "accepted", "secret": "wrong answer"},
...     "mixed/failing.java": {"secret/huge/graph07": {"allowed": ["TLE", "RTE"]}}
... }
>>> registry = Registry(exp_dict)

Expectations for a submission can now be extracted. Here, `accepted/ragnar.cpp`
is matched by the `accepted/` patterns, so those will be the expectations
for that submission.

>>> ragnar_expectations = registry.expectations("accepted/ragnar.cpp")

Compared with actual validation results:

>>> results_ac = { "sample/1": "AC", "secret/1": "AC", "secret/2": "AC" }
>>> results_wa = { "sample/1": "WA", "secret/1": "AC", "secret/2": "WA" }
>>> ragnar_expectations.is_satisfied_by(results_ac)
True

Altenatively, check the submission and results directly in the registry:

>>> registry.check_submission("accepted/ragnar.cpp", results_ac)
True
>>> registry.check_submission("accepted/ragnar.cpp", results_wa)
False
>>> registry.check_submission("wrong_answer/th.py", results_wa)
False
>>> results_wa_secret = { "sample/1": "AC", "secret/1": "AC", "secret/2": "WA" }
>>> registry.check_submission("wrong_answer/th.py", results_wa_secret)
True

Checking some results against no relevant expectations always succeeds:
>>> registry.check_submission("mixed/failing.java", results_wa_secret)
True
>>> registry.check_submission("mixed/failing.java", {"secret/huge/graph07": "WA" })
False
>>> registry.check_submission("mixed/failing.java", {"secret/huge/graph07": "TLE" })
True

Terminology
-----------

verdict
    A testcase can have a verdict, which is any of 'AC', 'WA', 'RTE', 'TLE'.
    (Note that the verdict 'JE' is never expected.)

result
    a verdict for a path representing a testcase, like "TLE" for "secret/huge/random-01"

score
    A finite number, often just an integer in the range {0, ..., 100}, but can be a float.
    NOT IMPLEMENTED

range
    A string of two space-separated numbers, like '0 30' or '-inf 43' or '3.14 3.14'; 
    a one-value range can be abbreviated: '5' is the range '5 5'.
    NOT IMPLEMENTED
"""

from functools import lru_cache


class Expectations:
    """The expectations for a submission.


    >>> e = Expectations("wrong answer")
    >>> e._required_verdicts
    {'': {'WA'}}
    >>> e._allowed_verdicts == {'': {'AC', 'WA'}}
    True
    >>> e.is_allowed_verdict("sample/1", "AC")
    True
    >>> e.is_allowed_verdict("sample/1", "RTE")
    False
    >>> unexpected_results = {"sample/1": "AC", "secret/1": "AC", "secret/2": "AC"}
    >>> expected_results = {"sample/1": "AC", "secret/1": "AC", "secret/2": "WA"}
    >>> missing = e.missing_required_verdics(unexpected_results)
    >>> missing[""]
    {'WA'}
    >>> missing = e.missing_required_verdics(expected_results)
    >>> missing[""]
    set()
    >>> (e.is_satisfied_by(expected_results), e.is_satisfied_by(unexpected_results))
    (True, False)

    Specify expectations by testgroup:

    >>> f = Expectations({'sample': 'accepted', 'secret': 'wrong answer'})
    >>> f._allowed_verdicts == {'sample': {'AC'}, 'secret': {'AC', 'WA'}}
    True
    >>> f._required_verdicts['secret']
    {'WA'}
    """

    def __init__(self, expectations: str | list[int | float] | dict):
        """
        Arguments
        ---------

        expectations
            list of common expectations, or range, or map
        """

        self._allowed_verdicts: dict[str, set[str]] = dict()
        self._required_verdicts: dict[str, set[str]] = dict()

        def set_common(pattern, abbreviation):
            if abbreviation == "accepted":
                self._allowed_verdicts[pattern] = set(["AC"])
                self._required_verdicts[pattern] = set(["AC"])
            elif abbreviation == "wrong answer":
                self._allowed_verdicts[pattern] = set(["AC", "WA"])
                self._required_verdicts[pattern] = set(["WA"])
            elif abbreviation == "time limit exceeded":
                self._allowed_verdicts[pattern] = set(["AC", "TLE"])
                self._required_verdicts[pattern] = set(["TLE"])
            elif abbreviation == "runtime exception":
                self._allowed_verdicts[pattern] = set(["AC", "RTE"])
                self._required_verdicts[pattern] = set(["RTE"])
            elif abbreviation == "does not terminate":
                self._allowed_verdicts[pattern] = set(["AC", "RTE", "TLE"])
                self._required_verdicts[pattern] = set(["RTE", "TLE"])
            elif abbreviation == "not accepted":
                self._required_verdicts[pattern] = set(["RTE", "TLE", "WA"])
            else:
                assert False, f"unknown abbreviation {abbreviation}"

        def parse_expectations(pattern, expectations):
            if isinstance(expectations, str):
                set_common(pattern, expectations)
            elif isinstance(expectations, list):
                pass  # NOT IMPLEMENTED
            elif isinstance(expectations, dict):
                for k, v in expectations.items():
                    if k.startswith("sample") or k.startswith("secret"):
                        if pattern != "":
                            assert False  # only allowed on top level!
                        parse_expectations(k, v)
                    elif k == "allowed":
                        self._allowed_verdicts[pattern] = v if isinstance(v, set) else set(v)
                    elif k == "required":
                        self._required_verdicts[pattern] = v if isinstance(v, set) else set(v)
                    elif k in ["judge_message", "score", "fractional_score"]:
                        pass  # NOT IMPLEMENTED
                    else:
                        assert False  # unrecognised key

        parse_expectations("", expectations)

    def is_allowed_verdict(self, path, verdict: str):
        """Is the result allowed for the testcase at the given path?"""
        for long, short in [
                ("ACCEPTED", "AC"),
                ("WRONG_ANSWER", "WA"),
                ("TIME_LIMIT_EXCEEDED", "TLE"),
                ("RUN_TIME_ERROR", "RTE")
                ]:
            if verdict == long:
                verdict = short

        for pattern, allowed in self._allowed_verdicts.items():
            if path.startswith(pattern) and verdict not in allowed:
                return False
        return True

    def missing_required_verdics(self, results: dict[str, str]) -> dict[str, set[str]]:
        """Which verdicts are missing?"""

        return {
            pattern: set(
                required_verdict
                for required_verdict in self._required_verdicts[pattern]
                if all(
                    results[path] != required_verdict
                    for path in results
                    if path.startswith(pattern)
                )
            )
            for pattern in self._required_verdicts
        }

    def is_satisfied_by(self, results: dict[str, str]) -> bool:
        """Are all requirements satisfied?"""
        missing = self.missing_required_verdics(results)
        return all(self.is_allowed_verdict(path, results[path]) for path in results) and all(
            not missing_verdict for missing_verdict in missing.values()
        )

class Registry:
    """ Maps string that describe submissions to Expectation objects. """
    def __init__(self, registry):
        self.registry = { pat: Expectations(registry[pat]) for pat in registry }


    def __str__(self):
        return str(self.registry)

    @lru_cache
    def expectations(self, submission_path):
        """ The expectations for a given submission. 
            *Should* return the most specific match. (Currently assumes
            there's exactly one.)
        """
        expectations = None
        for pat, exp in self.registry.items():
            if submission_path.startswith(pat):
                if expectations is not None:
                    assert False # NOT IMPLEMENTED: every pattern can match at most once
                expectations = exp
        if expectations is None:
            assert False # NOT IMPLEMENTED: every submission must match
        return expectations

    def check_submission(self, submission_path: str, results) -> bool:
        """ Check that given results were expected for the submission at the given path. """
        expectations = self.expectations(submission_path)
        return expectations.is_satisfied_by(results)



if __name__ == "__main__":
    import doctest

    doctest.testmod()
