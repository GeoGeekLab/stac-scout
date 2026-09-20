# Wildfire impact: live evidence to replay

This example exercises the complete STAC Scout decision path against a real STAC API. Remote
catalog contents can change, so exact Item counts are observations rather than golden test values.
The deterministic contracts behind the workflow are covered separately by CI and `evals/`.

The AOI is a small polygon around Lahaina, Maui, and the Item window begins after the August 2023
fire. A scientifically complete before/after impact study still requires an explicit comparison
window; STAC Scout intentionally does not invent it.

## 1. Confirm task requirements

```bash
stac-scout advise examples/wildfire-impact/request.json --task wildfire_impact
```

Expected semantics:

```text
data_type: optical
required measurements: nir + swir22
temporal strategy: before_after
follow-up: comparison_windows
```

The checked-in request already carries the required modality and measurements so the remaining
live steps use the same explicit hard constraints.

## 2. Federate candidate discovery

```bash
stac-scout federate examples/wildfire-impact/request.json \
  --max-workers 4 --overall-timeout 30
```

Inspect `candidates[]`, `duplicate_groups[]`, and typed `failures[]`. A provider failure does
not erase candidates from other providers.

## 3. Verify actual Items

For a stable concrete path, use Element 84 Earth Search and Sentinel-2 L2A:

```bash
stac-scout verify examples/wildfire-impact/request.json \
  --provider earth-search \
  --collection sentinel-2-l2a \
  --max-items 20
```

The result records observed Item IDs, timestamps, asset keys, AOI coverage, and warnings. If the
provider returns exactly the cap, the observation is `limit_reached` rather than falsely called
complete.

## 4. Produce the asset plan, volume evidence, manifest, and recipe

```bash
stac-scout plan examples/wildfire-impact/request.json \
  --provider earth-search \
  --collection sentinel-2-l2a \
  --max-items 20 \
  --manifest scout.manifest.json \
  --recipe load.py
```

Inspect:

- `access_plan.asset_choices[]` for measurement-to-asset evidence;
- each resampling decision and its evidence;
- `estimated_bytes` when `file:size` metadata is available, otherwise explicit UNKNOWN;
- output grid `utm` at 20 m;
- search completeness and selected Item IDs in `scout.manifest.json`.

The recipe is generated from the manifest; the manifest is the provenance record.

## 5. Replay the observation

```bash
stac-scout replay scout.manifest.json
```

Replay reports complete/partial/inconclusive comparison status plus confirmed and unresolved
missing/new Item IDs. A capped historical or current search is never promoted into false
confirmed drift.

## What this demo proves

```text
task semantics
  → cross-provider candidates
  → live Item evidence
  → asset selection evidence
  → resampling evidence
  → volume estimate or UNKNOWN
  → versioned manifest
  → completeness-aware replay
```

It does not claim that one post-fire window alone is a complete wildfire impact analysis.
