# STAC Scout

Evidence-backed dataset selection and verification for STAC catalogs.

**Find it. Check it. Use it.**

STAC Scout is a deterministic decision layer above STAC APIs. It helps answer:

> What data does this geospatial task actually require, which datasets fit, does matching data exist, and how can the decision be reproduced?

It does not replace `pystac-client`, `odc-stac`, or a STAC API.

## What it does

- converts structured intent into explicit geospatial data requirements
- derives task-specific data needs from a versioned rule registry
- inspects STAC API capabilities before using optional features
- normalizes collection metadata into a stable dataset model
- evaluates hard constraints with `pass` / `fail` / `unknown` semantics
- verifies item availability and AOI coverage
- resolves requested measurements to declared assets and bands
- estimates windowed transfer volume when size metadata exists
- emits replayable manifests and `odc-stac` recipes
- federates discovery across providers without hiding failures
- groups cross-catalog duplicates conservatively
- reports provider health separately from scientific ranking

## Design rules

- Never infer what can be inspected.
- Natural-language parsing may identify a task, but deterministic rules derive its data needs.
- Required and preferred measurements are different contracts.
- Task rules never invent comparison dates or sampling windows.
- Explicit user constraints are preserved over task defaults.
- Collection metadata is candidate evidence, not proof of item availability.
- `intersects` is not the same as AOI coverage.
- Unknown metadata is not a failed constraint.
- Probable duplicates remain visible; only strong identities are safe to collapse.
- Provider health is operational evidence, not scientific ranking evidence.

## Install

```bash
python -m pip install -e ".[dev]"
```

Python 3.12 or newer is required.

## Geo Task Intelligence

List the built-in task archetypes:

```bash
stac-scout tasks
stac-scout task-profile wildfire_impact
```

Derive data requirements from an existing request:

```bash
stac-scout advise request.json --task wildfire_impact
```

The result contains:

- the original task profile
- an enriched `ScoutRequest`
- every derived requirement with `rule_id`, rationale, and strength
- follow-up requirements such as missing comparison windows
- notes when explicit user constraints differ from task defaults

Task rules live in `src/stac_scout/data/tasks.toml`. Scientific basis and caveats are documented in [`docs/TASK_RULES.md`](docs/TASK_RULES.md).

## Intent contract

STAC Scout does not embed a model SDK. Applications can give any structured-output model the extraction contract:

```bash
stac-scout intent-contract
stac-scout schema intent
```

An `IntentDraft` may include a `task_type`. The model is not asked to invent spectral measurements from that task; the task registry owns those derivations.

Resolve a draft without task advice:

```bash
stac-scout resolve-intent intent.json
```

Resolve and apply task intelligence:

```bash
stac-scout advise-intent intent.json
```

Missing or ambiguous information remains unresolved and blocks conversion to a `ScoutRequest`.

## Providers

```bash
stac-scout providers
stac-scout health
```

The default enabled providers are Element 84 Earth Search and Microsoft Planetary Computer.

## Discovery and federation

```bash
stac-scout discover request.json --provider earth-search
stac-scout federate request.json
```

Federation keeps provider candidates visible. `sci:doi` produces an exact identity; weaker semantic matches are never silently collapsed.

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

## Architecture

```text
natural language
      │
  IntentDraft
      │ task_type
      ▼
  TaskAdvisor ───── TaskRegistry
      │              rules + sources
      ▼
 enriched ScoutRequest
      │
      ├── ScoutEngine
      │     ├── normalization
      │     ├── constraints
      │     ├── live verification
      │     ├── AOI coverage
      │     └── access planning
      │
      └── FederatedScout
            ├── provider isolation
            ├── dataset identity
            └── explicit failures
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

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
