# COL333 Assignment 1 checker

## Evaluate

Clone this repository into the root of your project.

```bash
git clone https://github.com/AbhinavPJ/COL333-A1-CHECKER.git checker
```

The checker expects exactly one submission in the project root, with these
files:

```text
part_a.py
part_b.py
```

From the project root, run:

```bash
python checker/check.py --part both
```

Use `--part a` or `--part b` to run one part. By default, all bundled test
suites are checked. A run passes when the output is valid; for Part B, the
checker also compares the submitted objective with the model solution and
reports whether it matches, is better, or is worse.

Useful options:

```bash
python checker/check.py --tests suite_003 --part b
python checker/check.py --tests suite_003 --timeout 30
python checker/check.py --list
```

The checker writes temporary outputs outside the project and requires only
the Python standard library.

## Contributing

Contributions to the checker are welcome. You can:

- Add test cases under `test-cases/<suite>/`.
- Add or update the corresponding model solutions under `model-solutions/<suite>/`.
- Add new suites, generators, verifier improvements, or other checker fixes.
- Create a pull request with your changes.
