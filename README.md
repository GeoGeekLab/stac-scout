# STAC Scout

Evidence-backed dataset selection and verification for STAC catalogs.

**Find it. Check it. Use it.**

STAC Scout is a deterministic decision layer above STAC APIs. It helps answer a more useful question than "how do I query STAC?":

> Which dataset fits this request, does matching data actually exist, what assets are needed, and how can the decision be reproduced?

It does not replace `pystac-client`, `odc-stac`, or a STAC API.

## What it does

- inspects STAC API capabilities before using optional features
- normalizes collection metadata into a stable dataset model
- evaluates hard constraints with `pass` / `fail` / `unknown` semantics
- verifies item availability and AOI coverage
- resolves requested measurements to declared assets and bands
- estimates windowed transfer volume when size metadata exists
- emits replayable manifests and `odc-stac` recipes
- federates discovery across multiple providers without hiding failures
- groups cross-catalog duplicates conservatively
- exposes a model-neutral natural-language intent contract
- reports provider health without contaminating scientific ranking

## Design rules

- Never infer what can be inspected.
- Collection metadata is candidate evidence, not proof of item availability.
- `intersects` is not the same as AOI coverage.
- Unknown metadata is not a failed constraint.
- Probable duplicates remain visible; only strong identities are safe to collapse.
- Provider health is operational evidence, not scientific ranking evidence.
- Natural-language parsing may produce unresolved fields; it must not invent coordinates or dates.
- Core verification remains deterministic; language models stay at the edge.

## Install

```bash
python -m pip install -e ".[dev]"
```

Python 3.12 or newer is required.

Planetary Computer access recipes use Microsoft's official signing SDK:

```bash
python -m pip install -e ".[planetary-computer]"
```

## Intent contract

STAC Scout does not embed a model SDK in the core package. Applications can give any structured-output model the extraction contract:

```bash
stac-scout intent-contract
stac-scout schema intent
```

A model returns an `IntentDraft`. Missing or ambiguous requirements belong in `unresolved`; Scout refuses to convert the draft into a `ScoutRequest` until they are resolved.

```bash
stac-scout resolve-intent intent.json
```

## Providers

Built-in provider metadata is packaged in `src/stac_scout/data/providers.toml`.

```bash
stac-scout providers
stac-scout providers --all
stac-scout health
stac-scout health --provider earth-search
```

The default enabled providers are Element 84 Earth Search and Microsoft Planetary Computer. NASA CMR-STAC remains recorded but disabled until a dedicated adapter handles its provider-specific catalog structure.

## Discovery and federation

Discover from a registered provider:

```bash
stac-scout discover request.json --provider earth-search
```

Or use a raw STAC endpoint:

```bash
stac-scout discover request.json \
  --catalog https://earth-search.aws.element84.com/v1
```

Federate across enabled providers:

```bash
stac-scout federate request.json
```

Federation keeps provider candidates visible. `sci:doi` produces an `exact` identity; matching collection/platform/instrument metadata produces only a `probable` identity and is never silently collapsed.

## Verify and plan

```bash
stac-scout verify request.json \
  --provider earth-search \
  --collection sentinel-2-l2a

stac-scout plan request.json \
  --provider earth-search \
  --collection sentinel-2-l2a \
  --manifest scout.manifest.json \
  --recipe load.py

stac-scout replay scout.manifest.json
```

For Planetary Computer, generated recipes use `planetary_computer.sign_inplace` rather than reimplementing SAS token handling.

## Live checks

Normal CI is deterministic and does not depend on external services. A separate manual GitHub Actions workflow runs provider health and live federated discovery:

```bash
python evals/live.py
```

## Architecture

```text
natural language
      │
  IntentDraft
      │
  ScoutRequest
      │
      ├── ProviderRegistry ── health observations
      │
      ├── ScoutEngine
      │     ├── normalization
      │     ├── constraints
      │     ├── live item verification
      │     ├── AOI coverage
      │     └── access planning
      │
      └── FederatedScout
            ├── provider isolation
            ├── dataset identity
            ├── duplicate groups
            └── explicit failures
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for module boundaries and invariants.

## Development

```bash
ruff check .
ruff format --check .
mypy
pytest --cov=stac_scout --cov-report=term-missing
python evals/runner.py
python -m build
```

CI runs on Python 3.12 and 3.13. Coverage must stay at or above 90%.

## License

MIT
