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
- federates discovery across multiple catalogs without hiding provider failures
- groups cross-catalog duplicates conservatively using evidence-backed identity rules

## Design rules

- Never infer what can be inspected.
- Collection metadata is candidate evidence, not proof of item availability.
- `intersects` is not the same as AOI coverage.
- Unknown metadata is not a failed constraint.
- Dataset recommendations must carry evidence and caveats.
- Probable duplicates remain visible; only strong identities are safe to collapse.
- Provider-specific access belongs behind adapters and manifests.
- Core verification stays deterministic; language models belong at the edges.

## Install

```bash
python -m pip install -e ".[dev]"
```

Python 3.12 or newer is required.

Planetary Computer access recipes use Microsoft's official signing SDK:

```bash
python -m pip install -e ".[planetary-computer]"
```

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

## Providers

Built-in provider metadata lives in `src/stac_scout/data/providers.toml`.

```bash
stac-scout providers
stac-scout providers --all
```

The default enabled providers are:

- Element 84 Earth Search
- Microsoft Planetary Computer

NASA CMR-STAC is recorded but disabled until a dedicated provider adapter handles its provider-specific catalog structure.

## CLI

Inspect a catalog's advertised capabilities:

```bash
stac-scout inspect-catalog https://earth-search.aws.element84.com/v1
```

Discover candidates from a raw catalog URL:

```bash
stac-scout discover request.json \
  --catalog https://earth-search.aws.element84.com/v1
```

Or use a registered provider:

```bash
stac-scout discover request.json --provider earth-search
```

Federate discovery across the enabled provider registry:

```bash
stac-scout federate request.json
```

Limit federation to explicit providers:

```bash
stac-scout federate request.json \
  --provider earth-search \
  --provider planetary-computer
```

Federation keeps each provider candidate visible. Exact identifiers such as `sci:doi` produce `exact` identity groups. Matching collection/platform/instrument metadata produces only `probable` groups and is not silently collapsed.

Verify live item availability:

```bash
stac-scout verify request.json \
  --provider earth-search \
  --collection sentinel-2-l2a
```

Build an access plan, manifest, and runnable recipe:

```bash
stac-scout plan request.json \
  --provider earth-search \
  --collection sentinel-2-l2a \
  --manifest scout.manifest.json \
  --recipe load.py
```

For Planetary Computer, the generated recipe uses `planetary_computer.sign_inplace` rather than reimplementing SAS token handling.

Replay a manifest later:

```bash
stac-scout replay scout.manifest.json
```

Replay reports which item IDs were retained, disappeared, or appeared since the manifest was created.

## Architecture

```text
ScoutRequest
    │
    ├── ProviderRegistry
    │       └── adapter factory
    │
    ├── single-catalog ScoutEngine
    │       ├── collection normalization
    │       ├── deterministic constraints
    │       ├── live item probe
    │       ├── AOI coverage
    │       ├── asset semantics
    │       └── access planning
    │
    └── FederatedScout
            ├── provider-isolated discovery
            ├── cross-catalog identity
            ├── duplicate groups
            └── provider failures
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for module boundaries and invariants.

## Repository layout

```text
src/stac_scout/          Core package
src/stac_scout/data/     Built-in provider registry
evals/                   Offline decision-contract evaluations
skill/                   Agent-facing operating rules
tests/                   Unit tests
.github/                  CI
```

## Current scope

`0.2.x` adds provider-aware federation while keeping the core deterministic. Place-name resolution and natural-language intent parsing remain outside the core request model. A caller may resolve those inputs before invoking Scout.

The next milestones are richer cross-provider dataset equivalence, provider health observations, live federation evaluations, and an optional natural-language request parser.

## Development

```bash
ruff check .
ruff format --check .
mypy
pytest --cov=stac_scout --cov-report=term-missing
python evals/runner.py
python -m build
```

CI runs on Python 3.12 and 3.13. Coverage must remain at or above 90%, the offline evaluation corpus must pass, and the built wheel must contain the provider registry.

## License

MIT
