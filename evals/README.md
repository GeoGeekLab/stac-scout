# Evaluations

The offline evaluation corpus tests decision contracts rather than model wording.

- `cases/` covers request invariants.
- `federation_cases/` covers cross-catalog identity and deduplication.
- `task_cases/` covers deterministic geospatial task derivations.
- `regression_matrix.json` binds each hardening acceptance scenario to concrete pytest node IDs; the runner fails if a required scenario or referenced test disappears.

Run deterministic evaluations with:

```bash
python evals/runner.py
```

Live provider observations are separate because remote state changes over time:

```bash
python evals/live.py
```

The deterministic runner and pytest suite gate ordinary CI. Live provider observations stay separate because remote catalogs are mutable; the GitHub workflow **Live provider checks** is manual and non-gating.
