# STAC Scout

Evidence-backed dataset selection and verification for STAC catalogs.

**Find it. Check it. Use it.**

STAC Scout is a deterministic decision layer above STAC APIs. It helps answer a narrower and more useful question than "how do I query STAC?":

> Which dataset fits this request, does matching data actually exist, what assets are needed, and how can the decision be reproduced?

It does not replace `pystac-client`, `odc-stac`, or a STAC API.

## What it does

- inspects STAC API capabilities before using optional features
- normalizes collection metadata into a stable dataset model
- ranks collection candidates with transparent lexical scoring
- evaluates hard constraints with `pass` / `fail` / `unknown` semantics
- verifies item availability for an AOI and time range
- measures AOI coverage with ellipsoidal area
- resolves requested measurements to declared asset/band metadata
- estimates windowed transfer volume when `file:size` is available
- emits reproducible manifests and `odc-stac` recipes
- replays manifests to detect item-set drift

## Design rules

- Never infer what can be inspected.
- Collection metadata is candidate evidence, not proof of item availability.
- `intersects` is not the same as AOI coverage.
- Unknown metadata is not a failed constraint.
- Dataset recommendations must carry evidence and caveats.
- Core verification stays deterministic; language models belong at the edges.

## Install

```bash
python -m pip install -e ".[dev]"
```

Python 3.12 or newer is required.

## Request model

A request is explicit about the scientific and operational constraints:

```json
{
  "task": "vegetation analysis",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[103.8, 1.2], [104.0, 1.2], [104.0, 1.4], [103.8, 1.4], [103.8, 1.2]]]
  },
  "datetime": {
    "start": "2026-06-01T00:00:00Z",
    "end": "2026-06-30T23:59:59Z"
  },
  "data_type": "optical",
  "required_measurements": ["red", "nir"],
  "max_spatial_resolution_m": 10
}
```

Validate it:

```bash
stac-scout validate-request request.json
```

## CLI

Inspect a catalog's advertised capabilities:

```bash
stac-scout inspect-catalog https://earth-search.aws.element84.com/v1
```

Discover candidate collections:

```bash
stac-scout discover request.json \
  --catalog https://earth-search.aws.element84.com/v1
```

Verify live item availability:

```bash
stac-scout verify request.json \
  --catalog https://earth-search.aws.element84.com/v1 \
  --collection sentinel-2-l2a
```

Build an access plan, manifest, and runnable recipe:

```bash
stac-scout plan request.json \
  --catalog https://earth-search.aws.element84.com/v1 \
  --collection sentinel-2-l2a \
  --manifest scout.manifest.json \
  --recipe load.py
```

Replay a manifest later:

```bash
stac-scout replay scout.manifest.json
```

Replay reports which item IDs were retained, disappeared, or appeared since the manifest was created.

## Architecture

```text
ScoutRequest
    │
    ├── catalog capability inspection
    ├── collection normalization
    ├── deterministic constraints
    ├── live item probe
    ├── AOI coverage
    ├── asset semantics
    └── access planning
            │
            ├── Decision data
            ├── scout.manifest.json
            └── odc-stac recipe
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for module boundaries and invariants.

## Repository layout

```text
src/stac_scout/   Core package
providers/        Catalog registry and provider notes
evals/            Offline decision-contract evaluations
skill/            Agent-facing operating rules
tests/            Unit tests
.github/           CI
```

## Current scope

`0.1.x` focuses on the deterministic core. Place-name resolution and natural-language intent parsing are intentionally outside the core request model. A caller may resolve those inputs before invoking Scout.

Provider-specific adapters, cross-provider dataset identity, richer access-cost estimation, and an optional reasoning layer are later milestones.

## Development

```bash
ruff check .
ruff format --check .
mypy
pytest --cov=stac_scout --cov-report=term-missing
```

CI runs on Python 3.12 and 3.13. Coverage must remain at or above 90%.

## License

MIT
