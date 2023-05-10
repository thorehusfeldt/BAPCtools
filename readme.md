# BAPCtools Fork

This is a fork of [RagnarGrootKoerkamp/BAPCtools](https://github.com/RagnarGrootKoerkamp/BAPCtools) focussing on test groups and grading.

## Use Default Grader

`bt run` now runs the default grader described in [the specification](https://icpc.io/problem-package-format/spec/problem_package_format#default-grader-specification) and implemented in [Kattis/problemtools](https://github.com/Kattis/problemtools/tree/develop/support/default_grader).

In particular, it builds a tree (the *testdata tree*) defined by the directory structure of `data/` and aggregates the grades of all given testcases, resulting in a tree of grades.
If the verdict at the root disagrees with the verdict determined by `bt run`, it issues a warning.

The verdicts for the subtrees can be shown using `--gradetree_depth <depth>`, the default is depth 0 (so nothing about grading is normally printed and `run` behaves exactly as usual.)

![run --gradetree](doc/images/run-gradetree.png)
