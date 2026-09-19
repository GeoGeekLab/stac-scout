# Evaluations

The evaluation corpus tests decision contracts rather than model wording. Each case contains a structured request and expected properties that a future reasoning layer must preserve.

Run the offline validator with:

```bash
python evals/runner.py
```

Live catalog evaluations should be kept separate because remote availability changes over time.
