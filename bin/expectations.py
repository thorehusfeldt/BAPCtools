"""Set expectations for a submission. 

Can be defined from various sources.

- expliclty by a yaml-like structure as defined in submissions/expectations.yaml

- explicitly by the presence of @EXPECTED_RESULTS@ somewhere in the source code. This
  applies only to the final (root) verdict.

- implicitly from a directory name, for a submission residing in
      <problemname>/submissions/<dirname>
  where <dirname> can be 'accepted', 'wrong_answer', 'time_limit_exceeded', or 'run_time_error'.
  This applies only to the final (root) verdict.
"""

from pathlib import Path
from functools import lru_cache


class Expectations:
    """The expectations for a submission."""

    def __init__(
        self, expectations=None, expected_results=None, dirname=None, testdata_settings=None
    ):
        """Expectations can be specified in three different ways:
        (1) from the submission directory where the source code is placed
        (2) explicitly using the tag '@EXPECTED_RESULTS@:' in the source code
        (3) explicty using the expected_grades.yaml syntax

        Preferably, exactly one of these should be given; when more are given,
        they should agree. The first two can set only the topmost final verdict;
        the third can also specify scores, ranges, and expecations for subgroups 
        and individual testcases.

        Args:
          testdata_settings: If testdata_settings[path] exists, it is a dict that defines
            the testdata settings for the keys 'grader_flags' and 'range' for the node
            at that path. Otherwise these setting are inherited from ancestors and eventually
            defaults as per the specification.
            Here, 'path' is the string representation of a path relative to the testdata
            directory, such as 'sample' or 'secret/group1/013-tiny'. The root's path
            can be specified as the empty string '' or as '.'.

          dirname: corresponding to (1) above; any of 'accepted', 'wrong_answer',
            'time_limit_exceeded', 'run_time_error'; all other value are equivalent
            to 'dirname=None'.

          expected_results: corresponding to (2) above; a list of strings like 'ACCEPTED',
            'WRONG-ANSWER', in the @EXPECTED_RESULTS@ DOMjudge tradition.

          expectations: corresponding to (3) above; a string, list of verdicts, or map,
            as defined in 'expectations.yaml'.
        """
        self._testdata_settings: dict[Path, dict[str, str]] = (
            {Path(k): v for k, v in testdata_settings.items()}
            if testdata_settings is not None
            else {}
        )
        self._specified_verdicts:dict[Path, set[str]] = dict()
        self._specified_scores:dict[Path, str] = dict()

        # Populate _specified_{verdicts, scores} from expectations. This involves
        # recursively parsing the expectations, which may be a dict of dicts.
        def walk(exp, path):
            if isinstance(exp, dict):
                verdicts = exp.get('verdict')  # None, str, or list
                scores = exp.get('score')
                for key in exp:  # 'sample', 'secret', 'edgecases', '003-random', ...
                    if key in ['verdict', 'score']:
                        continue
                    walk(exp[key], path / key)
            else:
                verdicts = exp  # None, str or list
                scores = None
            if verdicts is None:  # nothing specified for this path
                return

            if isinstance(verdicts, str):
                verdicts = [verdicts]  # now verdicts is a list of strings
            self._specified_verdicts[path] = set(verdicts)

            # scores can only set if verdict is also set
            if scores is not None:
                if len(scores.split()) == 1:  # e.g., "24"; change to "24 24"
                    scores = scores + ' ' + scores
                # Sanity check: score should be a subrange of testdata settings' range
                exp_lo, exp_hi = map(float, scores.split())
                range_lo, range_hi = map(float, self.testdata_settings(path)['range'].split())
                if not range_lo <= exp_lo <= exp_hi <= range_hi:
                    raise ValueError(f"Expectation {scores} violates testdata setting")
            self._specified_scores[path] = scores

        walk(expectations, Path())

        # Now consider the two ways of setting the root expecation. First, look at dirname.
        dirnamemap = {
            "accepted": "AC",
            "wrong_answer": "WA",
            "time_limit_exceeded": "TLE",
            "run_time_error": "RTE",
        }
        dirname_verdict = set([dirnamemap[dirname]]) if dirname in dirnamemap else None

        # Second, look at verdict lists specified by @EXPECTED_RESULTS@
        if expected_results:
            if dirname_verdict is not None:
                raise ValueError(f"Don't set EXPECTED_RESULTS in directory {dirname}")
            domjudge_verdict_map = {
                    'CORRECT': 'AC',
                    'WRONG-ANSWER': 'WA',
                    'TIMELIMIT': 'TLE',
                    'RUN-ERROR': 'RTE',
            }
            if not all(v in domjudge_verdict_map for v in expected_results):
                raise ValueError(f"Invalid expected results {expected_results}")
            expected_results_short = set(domjudge_verdict_map[v] for v in expected_results)
        else:
            expected_results_short = None

        # Check that expectations from various sources are consistent; possibly update
        # root expectation
        for root_verdict in [dirname_verdict, expected_results_short]:
            if root_verdict is None:
                continue
            yaml_verdict = self._specified_verdicts.get(Path())
            if yaml_verdict:
                if yaml_verdict != root_verdict:
                    raise ValueError("Contradictory expectations for root")
            else:
                self._specified_verdicts[Path()] = root_verdict



    @lru_cache
    def __getitem__(self, node):
        """The expecations for the given node.

        Arguments:
          node: A string, like "sample" or "secret/group1/034-small".
            Empty string "" or "." means the root.

        Return:
          A tuple (verdicts, range); see the methods of those names.
        """
        path = Path(node)
        verdicts = self._specified_verdicts.get(path) or set(["AC", "WA", "TLE", "RTE"])
        scores = self._specified_scores.get(path) or "-inf inf"

        # Check if an AC expectation is implied by an ancestral expectation.
        # Such an inference happens unless various grader_flags say differently.
        if path != Path():
            parent = path.parent
            grader_flags = self.testdata_settings(parent)['grader_flags']
            if (
                (self.verdicts(parent) == set(['AC']))
                and 'accept_if_any_accepted' not in grader_flags
                and 'always_accept' not in grader_flags
                and not (node == 'sample' and 'ignore_sample' in grader_flags)
            ):
                if 'AC' not in verdicts:
                    raise ValueError(f"Conflicting expectations for {node}: {verdicts}")
                verdicts = set(['AC'])

        return (verdicts, scores)

    def verdicts(self, node=''):
        """The verdicts expected for this node.

        Arguments:
          node: A string, like "sample" or "secret/group1/034-small".
                Empty string "", ".", or missing argument means the root.
        return:
          A nonempty subset of {"AC", "WA", "TLE", "RTE"}
        """

        return self[node][0]

    def range(self, node=''):
        """The range of scores expected for this node.

        Arguments:
          node: A string, like "sample" or "secret/group1/034-small".
                Empty string "" or missing argument is the root.
        return:
          A string of two space-separated numbers, like "-inf inf" or "0 100" or "4.5 4.5"
        """
        return self[node][1]

    @lru_cache
    def testdata_settings(self, path):
        """Return the testdata settings of 'grader_flags' and 'range' for this path,
        possibly as implied by ancestors and defaults.
        """
        parent_settings = (
            self.testdata_settings(path.parent)
            if path != Path()
            else {'grader_flags': '', 'range': '-inf inf'}  # defaults according to specification
        )
        return parent_settings | (self._testdata_settings.get(path) or {})

    def is_expected(self, judgement, node=''):
        """Is the given judgement expected by the given node?

        Arguments:
          judgement: either a verdict as a string "AC" or a tuple (verdict, score)
            where score is a number.
          node: A string, like "sample" or "secret/group1/034-small".
            Empty string "" or missing argument is the root.

        """

        verdicts, score_range = self[node]
        if isinstance(judgement, tuple):
            verdict, score = judgement
            low, high = map(float, score_range.split())
            score_ok = low <= float(score) <= high
        else:
            verdict = judgement
            score_ok = True

        return verdict in verdicts and score_ok
