# Evaluations

The offline evaluation corpus tests decision contracts rather than model wording.

- `cases/` covers request invariants.
- `federation_cases/` covers cross-catalog identity and deduplication behavior.

Run deterministic evaluations with:

```bash
python evals/runner.py
```

Live provider observations are intentionally separate because remote state changes over time:

```bash
python evals/live.py
```

The GitHub workflow **Live provider checks** is manual and does not gate ordinary CI.
