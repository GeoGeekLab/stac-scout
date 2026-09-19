# STAC Scout

Evidence-backed dataset selection and verification for STAC catalogs.

**Find it. Check it. Use it.**

STAC Scout sits above STAC clients and catalogs. It turns a data need into a structured request, compares candidate collections, verifies live availability, inspects assets, and produces a reproducible decision record.

It does not replace `pystac-client`, `odc-stac`, or a STAC API.

## Status

Early development. The first milestone defines the public data model, command-line interface, provider registry, and evaluation format.

## Design rules

- Never infer what can be inspected.
- A collection-level claim is not item-level evidence.
- `intersects` is not the same as AOI coverage.
- Unknown metadata is not a failed constraint.
- Dataset recommendations must carry evidence and caveats.
- Core verification stays deterministic; language models are optional at the edges.

## Install

```bash
python -m pip install -e ".[dev]"
```

## CLI

Validate a request:

```bash
stac-scout validate-request request.json
```

Print the request schema:

```bash
stac-scout schema request
```

Show the package version:

```bash
stac-scout version
```

## Repository layout

```text
src/stac_scout/   Core package
tests/            Unit tests
providers/        Catalog registry
evals/            Evaluation cases
skill/            Agent-facing skill instructions
.github/           CI
```

## Roadmap

### Milestone 1 — Deterministic core

- STAC capability inspection
- collection normalization
- item availability probes
- AOI coverage checks
- asset and band normalization

### Milestone 2 — Access planning

- asset selection
- byte and pixel estimates
- output-grid and resampling plans
- `odc-stac` recipes
- replayable manifests

### Milestone 3 — Reasoning layer

- natural-language request parsing
- candidate explanation
- provider-aware trade-off summaries

### Milestone 4 — Federation

- cross-catalog discovery
- duplicate dataset detection
- provider comparison
- catalog health tracking

## Development

```bash
ruff check .
ruff format --check .
mypy
pytest --cov=stac_scout --cov-report=term-missing
```

## License

MIT
