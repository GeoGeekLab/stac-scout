# Evaluations

The evaluation corpus tests decision contracts rather than model wording.

- `cases/` covers request invariants such as required measurements and verification requirements.
- `federation_cases/` covers cross-catalog identity and deduplication behavior with synthetic metadata.

Run the offline validator with:

```bash
python evals/runner.py
```

Live catalog evaluations stay separate because remote availability changes over time.
