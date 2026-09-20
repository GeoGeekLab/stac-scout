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

Health distinguishes transport reachability from provider correctness:

- network and timeout failures are `unreachable`;
- authentication, protocol, capability, and malformed-metadata failures are `degraded`;
- typed failures expose HTTP status and whether the failure is considered retryable.

## Provider registry and adapters

`ProviderRegistry` loads packaged provider metadata. Network quirks live behind `CatalogAdapter`.

All built-in adapters can share one `ProviderNetworkPolicy`. The policy defines connect/read
timeouts, a bounded retry budget, exponential backoff with jitter, a hard retry-delay cap, and
the transient HTTP statuses eligible for retry. GET and POST are the only retried methods because
STAC Item Search may use POST while discovery metadata is normally retrieved with GET.

HTTP 408, transport timeouts, and connection failures map to typed network/timeout errors.
HTTP 429 maps to a typed rate-limit failure and respects `Retry-After` only up to the configured
maximum delay. Authentication, protocol, capability, and malformed-metadata failures are not
silently treated as transient network outages.

The Planetary Computer adapter records signing requirements while generated recipes use the official signing SDK.

## Normalization and constraints

Provider metadata is normalized into stable internal models. Constraint evaluation uses three states:

- `pass`: evidence satisfies the requirement
- `fail`: evidence contradicts the requirement
- `unknown`: the current evidence layer cannot establish the requirement

Unknown is intentionally distinct from failure.

Hard constraints are evaluated in stages rather than being treated as one flat filter:

```text
Collection evidence
  data_type / measurements / source resolution
        |
        | FAIL -> reject before ranking
        v
Item evidence
  cloud cover and other scene-level facts
        |
        | known FAIL -> exclude Item
        v
Planning evidence
  selected assets / estimated transfer volume
        |
        | FAIL -> refuse executable plan/manifest
        v
PASS or explicitly unresolved UNKNOWN
```

A later stage refines an earlier `unknown` for the same constraint. For example,
`max_cloud_cover` is unknown at Collection discovery and is evaluated against
`eo:cloud_cover` when Items are inspected. `max_data_volume_bytes` remains unknown
until assets are selected and their transfer size can be estimated.

The `access` request constraint is currently kept explicitly `unknown` when normalized
dataset/asset metadata does not provide enough evidence to distinguish the requested access
policy. Provider endpoint accessibility is not treated as proof that dataset assets satisfy an
open/free-data requirement.

Preferences are not hard constraints and do not override a hard-constraint failure.

## Verification

Collection extents are not proof of availability. Item search is required before Scout reports data as available.

AOI coverage does not intersect raw longitude/latitude coordinates directly. Polygon and MultiPolygon rings are normalized into a continuous longitude domain centered on the AOI, long edges are densified, and area ratios are measured in an AOI-centered WGS84 Lambert Azimuthal Equal Area projection. This keeps antimeridian-crossing and high-latitude coverage topology explicit while recording both AOI coverage and the fraction of each Item intersected by the AOI.

## Federation and identity

`FederatedScout` composes independent catalog engines. Expected typed provider failures do not abort the full discovery operation.

Federation uses bounded worker concurrency and an overall discovery deadline. Providers still
running when the deadline expires are reported as retryable `ProviderTimeoutError` failures.
Unexpected exceptions such as `RuntimeError` are deliberately re-raised instead of being
misreported as remote-provider outages.

Cross-catalog identity is conservative:

1. `sci:doi` → exact
2. collection ID plus platform/constellation/instrument evidence → probable
3. otherwise → catalog-local identity

Only exact groups are marked safe to collapse.

## Planning and provenance

Planning resolves requested measurements against declared asset and band metadata. It does not invent aliases or use asset-key alphabetical order as a semantic tie-breaker.

Asset selection ranks explicit evidence: source-resolution fit, presence across inspected Items, asset roles, key/band semantic match, raster media type, and declared GSD. A completely tied result remains ambiguous and blocks an executable plan rather than being guessed.

Source and output resolution are separate contracts:

- `max_source_resolution_m` is a hard suitability constraint on source data;
- `target_crs` is the explicit output CRS;
- `target_resolution_m` is an explicit meter-based output grid resolution and therefore requires a projected meter CRS or the odc-stac `"utm"` selector;
- the legacy input key `max_spatial_resolution_m` is accepted only as an alias for `max_source_resolution_m`;
- a source-resolution threshold is never reused as output resolution.

Resampling is also evidence-driven. Classification metadata and mask/quality roles select nearest-neighbor; known continuous measurement semantics select bilinear. Unknown semantics remain unresolved instead of silently defaulting to bilinear.

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
