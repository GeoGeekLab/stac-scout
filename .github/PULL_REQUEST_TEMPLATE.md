## Summary

Describe the concrete behavior changed by this PR and why the change is needed.

## Contract impact

- [ ] No public behavior changed.
- [ ] Public behavior changed and documentation/migration guidance is included.
- [ ] Request/response/schema semantics changed.
- [ ] Manifest/replay semantics changed.
- [ ] Provider/network behavior changed.

If a public contract changed, state the old and new behavior explicitly.

## Correctness checklist

- [ ] Hard constraints are enforced, rejected, or explicitly reported as UNKNOWN; none are silently ignored.
- [ ] Missing metadata remains UNKNOWN rather than being guessed.
- [ ] Provider-specific behavior stays behind adapters or declarative registries.
- [ ] Ranking cannot override a hard constraint failure.
- [ ] Geospatial assumptions (CRS, longitude wrapping, geometry validity, resolution) are explicit where applicable.
- [ ] Raster resampling/measurement semantics are explicit where applicable.
- [ ] Reproducibility/provenance implications are addressed where applicable.

## Tests and evals

- [ ] Added/updated regression tests for the behavior changed.
- [ ] Added/updated deterministic eval cases when decision semantics changed.
- [ ] `ruff check .`
- [ ] `ruff format --check .`
- [ ] `mypy`
- [ ] `pytest --cov=stac_scout --cov-report=term-missing`
- [ ] `python evals/runner.py`
- [ ] `python -m build`

## Security and external I/O

- [ ] No new external I/O or trust boundary.
- [ ] New/changed external I/O has explicit timeout/error handling and SSRF/trust-boundary considerations.
- [ ] No secrets, credentials, signed URLs, or sensitive provider responses are committed.

## Scope

- [ ] The PR is narrow enough to review independently.
- [ ] Unrelated refactors are excluded or split out.
- [ ] Follow-up work is linked to an issue or the hardening roadmap.

Related issue(s):
