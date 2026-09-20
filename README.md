<div align="center">

# STAC Scout

---

**Scout STAC catalogs before you commit the compute.**

A Python CLI for finding suitable datasets, checking real Items, choosing assets,
planning raster reads, and replaying the result later.

[![CI](https://img.shields.io/github/actions/workflow/status/GeoGeekLab/stac-scout/ci.yml?branch=main&style=flat-square&label=CI)](https://github.com/GeoGeekLab/stac-scout/actions/workflows/ci.yml)
[![release](https://img.shields.io/github/v/release/GeoGeekLab/stac-scout?style=flat-square&color=f97316)](https://github.com/GeoGeekLab/stac-scout/releases)
[![PyPI](https://img.shields.io/pypi/v/stac-scout?style=flat-square&color=2563eb)](https://pypi.org/project/stac-scout/)
[![license](https://img.shields.io/badge/license-MIT-16a34a?style=flat-square)](LICENSE)
[![python](https://img.shields.io/pypi/pyversions/stac-scout?style=flat-square&logo=python&logoColor=white)](https://pypi.org/project/stac-scout/)
[![typing](https://img.shields.io/badge/typing-strict-2563eb?style=flat-square)](pyproject.toml)

[Quickstart](#quickstart) ·
[Workflow](#workflow) ·
[Tasks](#task-intelligence) ·
[Providers](#providers) ·
[Planning](#asset-and-raster-planning) ·
[Replay](#manifests-and-replay) ·
[Examples](examples/) ·
[Contributing](CONTRIBUTING.md) ·
[Security](SECURITY.md) ·
[Releases](https://github.com/GeoGeekLab/stac-scout/releases)

<br>

<img src="docs/assets/mascot/scout-hero.webp" width="240" alt="Scout, the STAC Scout mascot">

**Find it. Verify it. Plan it. Replay it.**

</div>

## What is STAC Scout?

STAC Scout is a small decision layer for STAC workflows.

It helps answer the questions that usually show up between "I found a Collection" and
"my pipeline is ready to run":

- Which collections match the task and the hard constraints?
- Do matching Items actually exist for this AOI and time window?
- Which assets should be loaded?
- What resolution, CRS, resampling, and approximate transfer size should the read use?
- Can the same choice be inspected again after the catalog changes?

Scout works with normal STAC APIs. It does not replace
[pystac-client](https://github.com/stac-utils/pystac-client),
[odc-stac](https://github.com/opendatacube/odc-stac), or the provider itself.

## Quickstart

Install from PyPI:

```bash
python -m pip install stac-scout
```

Python 3.12, 3.13, and 3.14 are tested in CI.

Create a request:

```bash
cat > request.json <<'JSON'
{
  "task": "assess wildfire impact",
  "place": "Lahaina, Maui",
  "datetime": {
    "start": "2023-08-09T00:00:00Z",
    "end": "2023-08-20T23:59:59Z"
  }
}
JSON
```

Ask Scout what the task needs:

```bash
stac-scout advise request.json --task wildfire_impact
```

The task profile adds the dataset requirements it can derive and reports anything that still
needs to come from the caller.

Then move on to live catalogs:

```bash
stac-scout federate request.json

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

For a complete runnable walkthrough, see
[`examples/wildfire-impact/`](examples/wildfire-impact/).

## Workflow

Scout deliberately keeps the workflow boring and inspectable:

| Stage | CLI | What you get |
| --- | --- | --- |
| **Find** | `discover`, `federate` | candidate collections from one or more catalogs |
| **Verify** | `verify` | matching Items, timestamps, footprints, asset keys, cloud metadata when present |
| **Plan** | `plan` | selected assets, raster settings, estimated bytes, manifest, optional load recipe |
| **Replay** | `replay` | comparison against the saved manifest and current catalog state |

Typical single-provider run:

```bash
stac-scout discover request.json --provider earth-search
stac-scout verify request.json --provider earth-search --collection sentinel-2-l2a
stac-scout plan request.json --provider earth-search --collection sentinel-2-l2a
```

Typical multi-provider run:

```bash
stac-scout federate request.json --max-workers 4 --overall-timeout 30
```

## Task intelligence

Users usually know the job before they know the bands.

Scout ships versioned task profiles for common geospatial workflows:

```bash
stac-scout tasks
stac-scout task-profile wildfire_impact
```

A profile can define:

- optical or SAR modality;
- required and preferred measurements;
- temporal strategy;
- processing preferences;
- mask preferences;
- short scientific rationale and sources.

Apply one to a request:

```bash
stac-scout advise request.json --task wildfire_impact
```

For example, the wildfire profile requires NIR and SWIR2 and uses a before/after strategy.
If the comparison windows are not in the request, Scout asks for them instead of making them up.

Task rules live in
[`src/stac_scout/data/tasks.toml`](src/stac_scout/data/tasks.toml), with notes in
[`docs/TASK_RULES.md`](docs/TASK_RULES.md).

## Providers

The built-in provider registry currently enables:

- **Element 84 Earth Search**
- **Microsoft Planetary Computer**

List providers:

```bash
stac-scout providers
stac-scout providers --all
```

Check connectivity and adapter health:

```bash
stac-scout health
stac-scout health --provider earth-search
```

You can also point Scout at a raw STAC API:

```bash
stac-scout discover request.json \
  --catalog https://earth-search.aws.element84.com/v1
```

Provider-specific behavior stays behind adapters, including Planetary Computer signing.

## Federation

`federate` searches enabled providers concurrently and keeps provider failures separate.

```bash
stac-scout federate request.json \
  --max-workers 4 \
  --overall-timeout 30
```

Duplicate grouping is conservative:

- DOI match → exact identity;
- matching collection/platform/constellation/instrument metadata → probable identity;
- otherwise → local to that catalog.

Probable matches remain visible instead of being silently collapsed.

## Verification

Collection metadata is useful for discovery. Item Search is what tells you whether the requested
scene is there.

```bash
stac-scout verify request.json \
  --provider earth-search \
  --collection sentinel-2-l2a \
  --max-items 20
```

Verification reports, when available:

- Item IDs and datetimes;
- AOI coverage;
- asset keys;
- cloud metadata;
- provider warnings;
- whether the search hit its Item limit.

AOI coverage handles antimeridian-crossing and high-latitude geometry without treating raw
longitude/latitude as a flat Cartesian grid.

## Asset and raster planning

`plan` turns a verified collection into an explicit read plan.

```bash
stac-scout plan request.json \
  --provider earth-search \
  --collection sentinel-2-l2a \
  --max-items 20 \
  --manifest scout.manifest.json \
  --recipe load.py
```

The access plan can include:

- measurement → asset mapping;
- why an asset was selected;
- categorical vs continuous resampling choice;
- source GSD checks;
- target CRS and output resolution;
- provider signing requirements;
- estimated transfer bytes when `file:size` is available.

Source and output resolution are separate settings:

```text
max_source_resolution_m  # "is the source detailed enough?"
target_resolution_m      # "what output grid should I request?"
target_crs               # projected CRS or "utm"
```

If asset metadata is genuinely ambiguous, the plan stays unresolved instead of choosing a key
alphabetically.

## Manifests and replay

A plan can be saved as a versioned manifest:

```bash
stac-scout plan request.json \
  --provider earth-search \
  --collection sentinel-2-l2a \
  --manifest scout.manifest.json
```

Replay it later:

```bash
stac-scout replay scout.manifest.json
```

The manifest records the request, provider/catalog identity, search limit/completeness,
collection fingerprint, selected Item IDs, asset metadata needed by the plan, output settings,
warnings, and assumptions.

Replay reports retained, missing, new, and unresolved Item IDs plus collection metadata changes.

A capped search is not treated as a complete catalog snapshot.

## A few opinions

Scout is intentionally opinionated about a small number of things:

- hard constraints are checked before ranking;
- missing metadata stays unknown;
- an Item limit is not proof that the search was complete;
- explicit user choices beat task defaults.

That is most of the philosophy. The rest is code and tests.

## CLI

```text
stac-scout
├── version
├── validate-request
├── schema
├── intent-contract
├── resolve-intent
├── advise-intent
├── tasks
├── task-profile
├── advise
├── providers
├── health
├── inspect-catalog
├── discover
├── federate
├── verify
├── plan
└── replay
```

Use `--help` on any command:

```bash
stac-scout --help
stac-scout plan --help
```

## Examples

### Wildfire impact

[`examples/wildfire-impact/`](examples/wildfire-impact/) follows a real Lahaina use case through:

1. task requirements;
2. provider federation;
3. live Item verification;
4. asset selection;
5. volume estimation;
6. manifest generation;
7. replay.

Remote catalog contents can change, so the example documents the workflow rather than pinning a
magic Item count.

## Intent integration

The core package does not depend on an LLM SDK.

If another system produces structured user intent, use the built-in contract:

```bash
stac-scout intent-contract
stac-scout schema intent
stac-scout resolve-intent intent.json
stac-scout advise-intent intent.json
```

The rest of the pipeline is the same CLI and model layer used by hand-written requests.

## Development

<img src="docs/assets/mascot/scout-terminal.webp" width="300" align="right" alt="Scout working at a geospatial developer terminal">

Scout is happiest when the tests are boring.

```bash
git clone https://github.com/GeoGeekLab/stac-scout.git
cd stac-scout

python -m pip install -e ".[dev]"

ruff check .
ruff format --check .
mypy
pytest --cov=stac_scout --cov-report=term-missing
python evals/runner.py
python -m build
```

CI runs the deterministic suite on Python 3.12, 3.13, and 3.14. Python 3.15 prereleases are used
as a non-blocking compatibility signal.

Remote provider checks are separate:

```bash
python evals/live.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow.

<br clear="right">

## Repository map

```text
stac-scout/
├── src/stac_scout/
│   ├── catalogs/          # STAC adapters and network boundary
│   ├── data/              # provider + task registries
│   ├── discovery/         # candidate retrieval
│   ├── models/            # request/result contracts
│   ├── normalize/         # STAC metadata normalization
│   ├── planning/          # asset + raster planning
│   ├── provenance/        # manifest + replay
│   └── verify/            # Item checks and AOI coverage
├── evals/                 # deterministic compatibility corpus
├── examples/
│   └── wildfire-impact/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── MASCOT.md
│   └── TASK_RULES.md
└── tests/
```

## Scout, the mascot

The little field bug is **Scout**.

Its layered shell loosely mirrors Collection → Item → Asset, and the scanner is there because
looking first is cheaper than debugging the wrong dataset later.

Mascot files and usage notes live in [`docs/MASCOT.md`](docs/MASCOT.md).

## Release

The current package is published on PyPI and GitHub Releases:

```bash
python -m pip install stac-scout
stac-scout version
```

Release artifacts are built once, published through PyPI Trusted Publishing, checksum-recorded,
and attached to the matching GitHub Release.

See [`docs/RELEASE.md`](docs/RELEASE.md).

## Security

For security reports, use [SECURITY.md](SECURITY.md).

If STAC Scout is embedded in a hosted service, treat arbitrary catalog URLs as outbound network
input and apply the deployment's normal egress policy.

## License

[MIT](LICENSE)

---

<div align="center">

**STAC Scout**

`find → verify → plan → replay`

</div>
