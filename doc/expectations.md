# Expectations 0.9.0

This framework allows problem author to express their expecations for the behaviour of a submission on the test data.

## Test Case Verdict

The behaviour of a submission on a _single_ test case is summarised in a *verdict*.

The verdicts are:

* `AC`: Accepted. The submission terminates successfully. Its execution time is strictly within the time limit. The output vaidator accepts the submission output.
* `WA`: The submission terminates successfully. Its execution time is strictly within the time limimt. The output validator rejects the submission output.
* `TLE`: The submission does not terminate in time stricly within the time limit.
* `RTE`: The submission aborts stricly within the time limit with a runtime error.


## Common Expectations for a Submission

The expected behaviour of a submission on the test data often falls into a number of common classes, such as

* `accepted`: Every test case is `AC`.
* `wrong answer`: Every test case receives `AC` or `WA`;  _some_ test case receives `WA`.

More generally, an expectation consists of a set of _permitted_ verdicts (by default, _all_ verdicts) and set of _required_ verdicts (by default, _no_ verdicts).

* All test case must receive one of the permitted verdicts.
* Some test case must receive one of the required verdicts.

Thus, the common expectations above can be spelt out in terms of lists of verdicts.
For instance for the submission `mysubmission.cpp`:

```yaml
mysubmission.py: accepted
```

is the same as

```yaml
mysubmission.py:
  permitted: [AC]
```
Similarly, 

```yaml
mysubmission.py: time limit exceeded
```

is the same as

```yaml
mysubmission.py:
  permitted: [AC, TLE]
  required: [TLE]
```


## Specifying Expectations for Submissions

Expectations for submissions can be provided in a file `/submissions/expectations.yaml`.
A common tradition is specified like this:

```yaml
accepted: accepted
wrong_answer: wrong answer
time_limit_exceeded: time limit exceeded
runtime_exception: runtime exception
```
This would associate the expectation “accepted” with the submission `/submissions/accepted/mysubmission.cpp`.
The flexibility of the expectations framework is that it is agnostic about directory names; for instance you can put your crashing submissions in `/submissions/run_time_error/` and put other requirements on the submissions in `/submissions/mixed/`:

```yaml
run_time_error: runtime exception
mixed:
  permitted: [AC, WA, TLE]
  required: [WA]
```

For problems with subtasks, you can put all your non-100% submissions into `/submissions/partially_accepted`, or you can introduce `/submissions/subtask1/` or even `/submissions/brute_force_subtask` for this problem.

## Specification per Submission

You can target individual submissions by providing their name:

```yaml
mixed/alice.py:
  permitted: [AC, WA, TLE]
  required: [WA]
mixed/bob.py:
  permitted: [AC, WA, TLE]
  required: [TLE]
```

## Specification per Test Data

Top-level (“root”) expectations apply to all test data, but you can be more fine-grained and specify expectations for subdirectories of `/data`.
For instance, if you want all submission in `wrong_answer` to pass the sample inputs, you’d write:

```yaml
wrong_answer:
  sample: accepted
  secret: wrong answer
```

# Specification

## Terminology 

To fix terminology, a _testcase_ is uniquely identifed by its path, which is a string satisfying

```cue
#testcasepath: ~= "^(secret|sample)" & #path
```

A _testcase verdict_ is one of
```cue
#verdict: 'AC' | 'RTE' | 'WA' | 'TLE'
```

The _testcase result_ of running the submission on a testcase consists of 

* its `#verdict`.

## Pattern matching

Both submissions and testcases are identified by paths.
The path of a submission is relative to `/submissions/`, possibly including a suffix like `.py`.
The path of a testcase is relative to `/data/`, not including a suffix like `.in`.
The _parents_ of a path are the logical ancestors in the sense of Python's `pathlib.PurePath.parents`;
the parents of submission `accepted/th.py` is the singleton `["accepted"]`;
the parents of testcase `secret/group3/032-random-4` are `["secret", "secret/group3"]`.
A _pattern_ can contain the Unix-style wildcard `*`; it cannot be empty.

```cue
#filename =~ [a-zA-Z0-9][a-zA-Z0-9_.-]*[a-zA-Z0-9] # given by specification
#path: =~ "[a-zA-Z0-9_./-]+" # nonempty
#pattern: =~ "[a-zA-Z0-9_./*-]+" # can contain *
```

A path `P` _matches_ a pattern `Q` if `P` or any of the parents of `P` match `Q` in the sense of Python's `fnmatch.fnmatch`.
(In particular, it is case-insensitive.)

## Expectations and Conditions

An _expectation_ consist of any of:

* a nonempty set `P` of _permitted verdicts_. If not specified, `P` is the set of all verdicts.
* a set `R`, possibly empty, of _required verdicts_. If not specified, `R` is the empty set.

An expectation is _satisfied_ by a set `S` of testcase results if

* the verdict of _every_ result in `S` belongs to `P`,
* if `R` is not empty then  some verdict in `R` appears as the verdict of _at least one_ result in `S`,

An expectation associated with a pattern is satisfied if all testcases matching the pattern satisfy the expectation.
A submission must satisfy all expectations that it matches.

## Schema

```cue
#pattern: =~"[a-zA-Z0-9_./*-]+" // can contain *

#registry: close({[#pattern]: #root_expectation})

#verdict: "AC" | "WA" | "RTE" | "TLE"

#root_expectation: #abbreviation | {
    #expectation
    [=~"^(sample|secret|\\*)" & #pattern]: #abbreviation | #expectation
}

#expectation: {
    permitted?: [...#verdict] // only these verdicts may appear
    required?:  [...#verdict] // at least one of these verdicts must appear
    }

#abbreviation: "accepted" |  // { permitted: [AC] }
    "wrong answer" |         // { permitted: [AC, WA]; required: WA }
    "time limit exceeded" |  // { permitted: [AC, TLE]; required: TLE }
    "runtime exception" |    // { permitted: [AC, RTE]; required: RTE }
    "does not terminate" |   // { permitted: [AC, RTE, TLE]; required: [RTE, TLE] }
    "not accepted" |         // { required: [RTE, TLE, WA] }
    "rejected"               // { required: [RTE, WA] }```
```

# Examples

```yaml
# Simple examples for some common cases

a.py: accepted            # AC on all cases
b.py: wrong answer        # at least one WA, otherwise AC
c.py: time limit exceeded # at least one TLE, otherwise AC
d.py: runtime exception   # at least one RTE, otherwise AC
e.py: does not terminate  # at least one RTE or TLE, but no WA
f.py: not accepted        # at least one RTE, TLE, or WA

# submission are identified by path or parent:

wrong_answer: wrong answer # expectations "wrong answer" apply to "wrong_answer/th.py" etc.

# can also use globbing. Because we use YAML, better surround those strings in quotes

"accepted/*.py": accepted # matches {accepted/th.py, accepted/ragnar.py}
"*/th.py" : accepted    # matches {accepted/th.py, wrong_answer/th.py}.

# Abbreviations are just shorthands for richer maps 
# of "required" and "permitted" keys.
#
# For instance, these are the same:

th.py: accepted
---
th.py:
  permitted: [AC]
  required: [AC]
---

# Specify that a submission is failed by the output validator on some testcase
# These are the same:

wrong.py: wrong answer
---
wrong.py:
  permitted: [WA, AC]
  required: [WA]
---
wrong.py:
  permitted: # alternative yaml syntax for list of strings
    - WA
    - AC
  required: [WA]
---

# Specify that the submission fails, but passes the samples.
# These are the same, using the same abbreviations as
# above for "accepted" and "wrong answer"

wrong.py:
  sample: accepted
  secret: wrong answer
---
wrong.py:
  sample: 
    permitted: [AC]
    required: [AC]
  secret:
    permitted: [AC, WA]
    required: [WA]

# Expectations apply to testcases whose parent matches the pattern
funky.cpp:
  permitted: [AC, WA, RTE]
  secret:
      permitted: [AC, RTE, TLE] # TLE is forbidden at parent, so this does not suddenly allow TLE here; tool should warn
  secret/small: accepted # more restrictive than ancestor: this is fine
   
# Specification for testcases works "all the way down to the single tescase"
funkier.cpp:
  secret/huge_instances/disconnected_graph:
      permitted: [RTE, TLE]
        
# Testcases can also be addressed using the unix-like “globbing” wildcard `*`

brute_force.py:
  "*/*-small-*" : accepted # matches secret/group3/032-small-disconnected
```

# Roadmap 

## 0.9.1 Judge message

Extend `testcase result` to include the contents of  `judgemessage.txt`
Add expectations for judge message:

```cue
#expectation: {
    ...
    message?: string // this must appear in some judgemessage, case-insensitive
}
```

Should this match by substring, and case-insensitive? (Or by glob, regex, etc.)?
Possible rule:

* possibly a string `message`, the _required judge message_

* if `message` is specified then it appears (as a substring) in the judge message of _at least one_ result in `S`,

## 0.9.2 Richer globbing

Specify if `*` matches `x/y`.
Allow `**`, `[abc]` and `[^abc]` as per Python’s `fnmatch`. 
Specify `{th.py, ragnar.py}`.  

## 0.9.3 Scoring

Extend `testcase result` to include the score of the testcase.

```cue
#expectation: {
    ...
    score?: #range // all scores must be in range
}

#range: number | [number, number]

... #abbreviation | #range | #expectation
```

* possibly a `score` range, which is an interval `(a,b)` with `0 <= a <= b`.

* if `score` is specified then the score \(s\) computed for _every_ testcase in `S` satisfies `a <= s <= b`.

This requires understanding what we mean by “the score of a testcase”. (In particular, has the multiplier from `testdata.yaml` been applied?)

## 0.9.4 Aggregate results

```cue
#expectation: {
    ...
    aggregate_verdict?: #verdict
    aggregate_score?: #range
}
```

## 0.9.5 Timing

Introduce the restricted verdicts `AC!` and `TLE!`, or invent some other formalism.
