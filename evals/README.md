# Evaluations

The offline evaluation corpus tests decision contracts rather than model wording.

- `cases/` covers request invariants.
- `federation_cases/` covers cross-catalog identity and deduplication.
- `task_cases/` covers deterministic geospatial task derivations.

Run deterministic evaluations with:

```bash
python evals/runner.py
```

Live provider observations are separate because remote state changes over time:

```bash
python evals/live.py
```

The GitHub workflow **Live provider checks** is manual and does not gate ordinary CI.
