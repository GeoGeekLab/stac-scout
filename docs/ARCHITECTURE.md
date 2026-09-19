# Architecture

STAC Scout separates language interpretation, task knowledge, operational health, and geospatial verification.

## Intent boundary

`stac_scout.reasoning` defines a model-neutral structured extraction protocol. An application supplies the model; Scout supplies the `IntentDraft` schema and extraction rules.

The model may map an explicit user goal to a supported `task_type`, but it is explicitly told not to derive spectral measurements. Missing or ambiguous values remain in `unresolved`.

## Task intelligence

`TaskRegistry` loads declarative profiles from `stac_scout/data/tasks.toml`. Each profile has:

- a stable task identifier and rule ID
- required and preferred measurements
- a data-type default
- a temporal strategy
- processing and mask preferences
- rationale and source references

`TaskAdvisor` enriches a `ScoutRequest` without overwriting explicit user choices. Every derived value is returned as a `DerivedRequirement` with rule provenance.

Task defaults do not invent dates. A before/after task without explicit comparison windows returns `comparison_windows` in `follow_up_requirements`.

Task knowledge is intentionally outside prompts so it can be tested, versioned, reviewed, and reused with different language models.

## Provider health

`stac_scout.health` observes endpoint reachability, latency, STAC version, and Item Search support. Health is operational metadata only and never changes scientific dataset scores.

## Provider registry and adapters

`ProviderRegistry` loads packaged provider metadata. Network quirks live behind `CatalogAdapter`.

The Planetary Computer adapter records signing requirements while generated recipes use the official signing SDK.

## Normalization and constraints

Provider metadata is normalized into stable internal models. Constraint evaluation uses three states:

- `pass`: metadata satisfies the requirement
- `fail`: metadata contradicts the requirement
- `unknown`: metadata is insufficient

Unknown is intentionally distinct from failure.

## Verification

Collection extents are not proof of availability. Item search is required before Scout reports data as available.

AOI coverage uses WGS84 ellipsoidal area and records both AOI coverage and the fraction of each item intersected by the AOI.

## Federation and identity

`FederatedScout` composes independent catalog engines. One provider failing does not abort the full discovery operation.

Cross-catalog identity is conservative:

1. `sci:doi` → exact
2. collection ID plus platform/constellation/instrument evidence → probable
3. otherwise → catalog-local identity

Only exact groups are marked safe to collapse.

## Planning and provenance

Planning resolves requested measurements against declared asset and band metadata. It does not invent aliases.

A manifest records request, provider, collection, item IDs, selected assets, signing strategy, query, warnings, and Scout version. Replay performs a fresh search and reports item-set drift.

## Dependency direction

```text
reasoning ──> IntentDraft
                  │
                  v
tasks.toml ──> TaskAdvisor ──> ScoutRequest
                               │
registry ──> adapters ─────────┤
                               v
                          ScoutEngine
                          /        \
                   federation    planning
                                    │
                               provenance

health is separate operational evidence
```

## Non-goals

The core does not provide a STAC server, raster processing engine, geocoder, general GIS agent, embedding database, multi-agent framework, or hidden task heuristics inside prompts.
