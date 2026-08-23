# Part A checker

Run from the repository root. No additional packages are required.

Add a new suite of 1,000 mixed test cases:

```bash
python checker/test_generator.py
```

Run `part_a.py` on every suite and replace the model solutions with its output:

```bash
python checker/check_a.py overwrite
```

Run `part_a.py` again and verify each output:

```bash
python checker/check_a.py evaluate
```

Test cases are written under `checker/test-cases/`. Model solutions are written under
`checker/model-solutions/`, and candidate solutions under `checker/solutions/`.

Evaluation uses `verifier.py` for H1-H9 validation. Expected infeasible cases are tracked in
the suite manifest and must produce `{}`. Candidate solutions are stored under
`checker/solutions/`.
