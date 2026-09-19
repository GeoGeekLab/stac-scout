<div align="center">

# STAC Scout

**Find the data. Prove it exists. Know what you're getting.**

`intent → task semantics → catalog federation → live item evidence → asset plan → manifest`

[![CI](https://github.com/GeoGeekLab/stac-scout/actions/workflows/ci.yml/badge.svg)](https://github.com/GeoGeekLab/stac-scout/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-3776AB?style=flat-square&logo=python&logoColor=white)](.github/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-2ea44f?style=flat-square)](LICENSE)
[![STAC](https://img.shields.io/badge/STAC-evidence--first-111111?style=flat-square)](https://stacspec.org/)

A deterministic decision layer for the STAC ecosystem.

</div>

## STAC is syntax. Dataset choice is semantics.

A model can generate a valid STAC query.

That does not mean it chose the right dataset.

A Collection can advertise the right spatial and temporal extent.

That does not mean an Item actually exists for your AOI and date.

An asset can be called `B08`.

That does not mean a caller should silently assume what it contains.

STAC Scout lives in that gap.

```text
"find imagery for this task"
            │
            ▼
      what does the task need?
            │
            ▼
      which datasets fit?
            │
            ▼
      do matching items exist?
            │
            ▼
      which assets are actually required?
            │
            ▼
      how much data will this read?
            │
            ▼
      can the decision be replayed?
```

The operating rule is simple:

> **Never infer what can be inspected.**

## What Scout actually does

```text
natural language / structured request
              │
              ▼
         IntentDraft
              │
        task_type + facts
              ▼
     ┌───────────────────┐
     │    TaskAdvisor   │◄──── versioned task rules
     └────────┬─────────┘
              │
              ▼
        ScoutRequest
              │
      ┌───────┴────────┐
      │                │
      ▼                ▼
 ScoutEngine     FederatedScout
      │                │
      │         provider isolation
      │         dataset identity
      │         duplicate evidence
      │         explicit failures
      │                │
      └───────┬────────┘
              ▼
         live Item probe
              │
        AOI coverage
              │
         asset semantics
              │
         access planning
              │
              ▼
      manifest + replay
```

Scout does **not** replace `pystac-client`, `odc-stac`, or a STAC API.

It decides what should be asked, checks what came back, and records why.

## The invariants

These are not style preferences. They are the contract.

- **Collection metadata is not availability evidence.** Item Search is.
- **`intersects` is not AOI coverage.**
- **Unknown is not false.**
- **Required and preferred measurements are different things.**
- **Task rules do not invent dates.**
- **Explicit user constraints beat defaults.**
- **Probable duplicates stay visible.**
- **Provider health is not scientific quality.**
- **A language model may classify intent; it does not own geospatial truth.**
- **Every useful decision should be reproducible.**

Or shorter:

```text
metadata ≠ evidence
similarity ≠ identity
availability ≠ suitability
confidence ≠ proof
```

## Install

```bash
python -m pip install -e ".[dev]"
```

Python 3.12 or newer is required.

For Planetary Computer access recipes:

```bash
python -m pip install -e ".[planetary-computer]"
```

## Geo Task Intelligence

The user often knows the problem, not the bands.

```text
"assess wildfire impact"
        ↓
optical
        ↓
NIR + SWIR2 required
        ↓
surface reflectance preferred
        ↓
before/after strategy
        ↓
comparison_windows still required from the user
```

Scout keeps that knowledge in a versioned, inspectable registry instead of hiding it in prompts.

List the built-in task archetypes:

```bash
stac-scout tasks
stac-scout task-profile wildfire_impact
```

Derive task-aware data requirements:

```bash
stac-scout advise request.json --task wildfire_impact
```

The output includes:

```text
TaskProfile
├── rule_id
├── rationale
├── sources
├── required measurements
├── preferred measurements
├── temporal strategy
├── processing preferences
└── mask preferences

TaskAdvice
├── enriched ScoutRequest
├── derivations[]
│   ├── rule_id
│   ├── field
│   ├── value
│   ├── required | preferred
│   └── rationale
├── follow_up_requirements[]
└── notes[]
```

Task rules live in:

```text
src/stac_scout/data/tasks.toml
```

The scientific basis and rule boundaries are documented in [`docs/TASK_RULES.md`](docs/TASK_RULES.md).

### Rules are allowed to say "I don't know"

For example, a before/after wildfire task does **not** cause Scout to hallucinate a pre-fire window.

It returns:

```json
{
  "follow_up_requirements": ["comparison_windows"]
}
```

Likewise, if the user explicitly asks for SAR while a task's default modality is optical, Scout preserves SAR and skips incompatible optical band defaults.

No spectral fan fiction.

## Intent boundary

STAC Scout deliberately does not ship an LLM SDK in the core package.

Any structured-output model can produce an `IntentDraft`.

Get the contract:

```bash
stac-scout intent-contract
stac-scout schema intent
```

The model may identify a supported `task_type`.

It is explicitly told **not** to invent:

- coordinates;
- dates;
- dataset names;
- measurement names;
- hidden constraints.

Those belong to deterministic code, explicit user input, or live metadata.

Resolve an intent directly:

```bash
stac-scout resolve-intent intent.json
```

Resolve it and apply task intelligence:

```bash
stac-scout advise-intent intent.json
```

If required information is still ambiguous, the draft stays unresolved.

That is a feature.

## Providers are adapters, not assumptions

List the built-in provider registry:

```bash
stac-scout providers
stac-scout providers --all
```

Check operational health:

```bash
stac-scout health
stac-scout health --provider earth-search
```

The default enabled providers are:

- Element 84 Earth Search
- Microsoft Planetary Computer

Provider quirks stay behind adapters.

Planetary Computer signing is recorded explicitly and generated recipes use the official `planetary_computer.sign_inplace` path instead of reimplementing SAS handling.

Provider latency and uptime are reported as operational evidence only.

A slow endpoint does not make a scientifically suitable dataset worse.

## Federation without pretending everything is the same

Search a single provider:

```bash
stac-scout discover request.json --provider earth-search
```

Or a raw STAC endpoint:

```bash
stac-scout discover request.json \
  --catalog https://earth-search.aws.element84.com/v1
```

Search across enabled providers:

```bash
stac-scout federate request.json
```

Dataset identity is conservative:

```text
sci:doi
  → exact

collection id + platform / constellation / instrument evidence
  → probable

everything else
  → local to that catalog
```

Only exact groups are considered safe to collapse.

Probable matches stay visible.

Because two catalogs agreeing on a name is not the same thing as two catalogs describing the same scientific product.

## The catalog says maybe. Items say yes or no.

Verification is item-level.

```bash
stac-scout verify request.json \
  --provider earth-search \
  --collection sentinel-2-l2a
```

Scout records:

- matching Item count;
- Item IDs;
- timestamps;
- asset keys;
- cloud metadata when available;
- AOI coverage ratio;
- fraction of each Item intersected by the AOI;
- warnings when geometry or metadata cannot be evaluated.

AOI area is measured geodesically on WGS84 rather than treating longitude/latitude as a flat Cartesian plane.

Because this is geospatial software.

## Asset planning

A scientifically correct Collection can still produce a bad access plan.

Scout resolves requested measurements against declared asset and band metadata rather than guessing asset names.

```bash
stac-scout plan request.json \
  --provider earth-search \
  --collection sentinel-2-l2a \
  --manifest scout.manifest.json \
  --recipe load.py
```

Planning can produce:

```text
measurement → asset
resampling strategy
windowed-read estimate
output resolution
provider signing requirements
warnings
odc-stac recipe
```

When `file:size` exists, Scout estimates transfer volume from the AOI/item intersection fraction.

It is an estimate, not a bandwidth prophecy.

## Manifests: because catalogs move

A successful query today is not a frozen scientific record.

Scout writes a manifest containing the decision inputs and observed Item set.

Replay it later:

```bash
stac-scout replay scout.manifest.json
```

Replay reports:

```text
retained Item IDs
missing Item IDs
new Item IDs
```

The manifest is evidence of the decision.

It is not a copy of the remote data.

## CLI map

```text
stac-scout
├── version
├── validate-request
├── schema
│
├── intent-contract
├── resolve-intent
├── advise-intent
│
├── tasks
├── task-profile
├── advise
│
├── providers
├── health
├── inspect-catalog
│
├── discover
├── federate
├── verify
├── plan
└── replay
```

## Repository map

```text
stac-scout/
├── src/stac_scout/
│   ├── catalogs/          # STAC access boundary
│   ├── data/
│   │   ├── providers.toml
│   │   └── tasks.toml
│   ├── discovery/         # candidate retrieval
│   ├── models/            # strict contracts
│   ├── normalize/         # provider metadata → stable models
│   ├── planning/          # assets, raster semantics, volume
│   ├── provenance/        # manifest + replay
│   ├── verify/            # live evidence + geodesic coverage
│   ├── federation.py
│   ├── health.py
│   ├── identity.py
│   ├── reasoning.py
│   ├── scout.py
│   ├── tasking.py
│   └── tasks.py
├── evals/
│   ├── cases/
│   ├── federation_cases/
│   ├── task_cases/
│   ├── runner.py
│   └── live.py
├── docs/
│   ├── ARCHITECTURE.md
│   └── TASK_RULES.md
├── skill/
│   └── SKILL.md
└── tests/
```

## Evals over vibes

The deterministic evaluation corpus checks contracts that affect dataset decisions:

```bash
python evals/runner.py
```

It covers:

- request invariants;
- cross-provider identity;
- task-derived measurements;
- task modality;
- temporal strategy;
- follow-up requirements.

Remote providers are intentionally kept out of ordinary CI.

Live checks run separately:

```bash
python evals/live.py
```

That separation is deliberate:

```text
deterministic behavior
  → CI gate

remote catalog state
  → live observation
```

## Development

```bash
ruff check .
ruff format --check .
mypy
pytest --cov=stac_scout --cov-report=term-missing
python evals/runner.py
python -m build
```

CI runs on Python 3.12 and 3.13.

Coverage must stay at or above 90%.

The wheel is also checked to ensure the provider and task registries are actually packaged.

## What Scout refuses to fake

```text
"the collection covers 2024, so data must exist"
"cloud_cover=8 means my AOI is clear"
"B08 probably means NIR"
"these two collections have similar names, merge them"
"the provider is fast, therefore the dataset is better"
"wildfire task means I'll invent a pre-fire date"
"the model sounded confident"
```

Those are shortcuts.

Scout's job is to turn them into inspectable claims.

## Philosophy

```text
STAC gives us a language.

Scout adds skepticism.
```

Or, in GeoGeek form:

> **The map can look right while the geography is wrong.  
> The query can run while the dataset choice is wrong.  
> Check the semantics. Check the evidence.**

## License

[MIT](LICENSE)

---

<div align="center">

**Find it. Verify it. Plan it. Replay it.**

`catalog metadata ≠ ground truth`

</div>
