# Architecture

STAC Scout keeps language interpretation, operational health, and geospatial verification separate.

## Intent boundary

`stac_scout.reasoning` defines a model-neutral `StructuredExtractor` protocol. Scout supplies strict extraction instructions and the `IntentDraft` JSON schema; an application supplies the model or service.

`IntentDraft` is intentionally less strict than `ScoutRequest`. Missing dates, locations, or ambiguous requirements stay in `unresolved`. `IntentDraft.to_request()` is the gate into the deterministic core and refuses unresolved input.

The intent layer does not geocode names, invent dates, choose datasets, or verify availability.

## Provider health

`stac_scout.health` observes endpoint reachability, response latency, STAC version, and Item Search support. Health is operational metadata only. It is never an input to scientific dataset scoring.

External health checks are kept out of normal CI. The manual live workflow runs health and federation smoke checks against real providers.

## Provider registry and adapters

`ProviderRegistry` loads packaged provider metadata from `stac_scout/data/providers.toml`. A provider records endpoint, adapter type, access mode, signing strategy, and whether it participates in default federation.

Network quirks belong behind `CatalogAdapter`. The Planetary Computer adapter records its signing requirement while generated recipes use the official `planetary_computer.sign_inplace` modifier.

The base adapter protocol deliberately remains provider-neutral so third-party adapters are not forced to implement registry metadata.

## Normalization and constraints

Provider metadata is converted to stable internal models. Normalization recognizes STAC 1.1 `bands` and legacy `eo:bands` / `raster:bands` forms.

Constraints use three states:

- `pass`: metadata satisfies the requirement
- `fail`: metadata contradicts the requirement
- `unknown`: metadata is insufficient

Unknown is intentionally distinct from failure.

## Verification

Collection extents are not proof of availability. Item search is required before Scout reports data as available.

AOI coverage uses WGS84 ellipsoidal area and records both AOI coverage and the fraction of an item intersected by the AOI. The latter supports first-order windowed read estimates.

## Federation and identity

`FederatedScout` composes independent single-catalog engines. One provider failing does not abort the whole discovery operation; the failure is returned explicitly.

Cross-catalog identity is conservative:

1. `sci:doi` → `exact`
2. collection ID plus platform/constellation/instrument evidence → `probable`
3. otherwise → catalog-local identity

Only exact groups are marked safe to collapse. Probable groups remain visible.

## Planning and provenance

Planning resolves requested measurements against declared asset and band metadata. It does not invent aliases.

When `file:size` exists, the planner estimates transfer volume using the item intersection fraction. Continuous measurements default to bilinear resampling; masks and classifications default to nearest-neighbor.

A manifest records request, provider, catalog, collection, item IDs, selected assets, signing strategy, query, warnings, and Scout version. Replay performs a fresh search and reports item-set drift.

## Dependency direction

```text
reasoning ──> IntentDraft ──> ScoutRequest
                              │
registry ──> adapters ────────┤
health     (separate)         │
                              v
                         ScoutEngine
                         /        \
                  federation    planning
                                   │
                              provenance
```

## Non-goals

The core does not provide a STAC server, raster processing engine, geocoder, general GIS agent, embedding database, multi-agent framework, or heuristic auto-merging of ambiguous datasets.
