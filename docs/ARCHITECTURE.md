# Architecture

STAC Scout separates language-facing intent from data-facing verification. The core package accepts a structured `ScoutRequest`; it does not guess missing geographic facts.

## Boundaries

### Provider registry

`stac_scout.registry` owns the built-in provider inventory. The canonical registry is packaged at `stac_scout/data/providers.toml` so provider metadata is available from an installed wheel as well as a source checkout.

A `ProviderSpec` records the endpoint, adapter type, access mode, asset-signing strategy, and whether the provider is enabled for default federation. Provider configuration is declarative; network behavior belongs in adapters.

### Catalog layer

`stac_scout.catalogs` owns remote STAC interaction. `GenericStacAdapter` delegates ordinary STAC operations to `pystac-client`; capability inspection reads the root and conformance documents directly so optional API features are explicit.

Provider-specific behavior belongs behind the `CatalogAdapter` protocol and adapter factory. The Microsoft Planetary Computer adapter records the required asset-signing strategy, while metadata discovery remains normal STAC access. Generated Planetary Computer recipes use the official `planetary_computer.sign_inplace` modifier rather than reproducing SAS logic.

The adapter protocol deliberately does not require provider metadata. Third-party adapters written against the earlier single-catalog interface remain valid; `ScoutEngine` treats provider identity and signing as optional adapter capabilities.

### Normalization layer

`stac_scout.normalize` converts provider metadata into stable internal models. The normalizer recognizes STAC 1.1 `bands` as well as the older `eo:bands` and `raster:bands` forms.

Normalization also extracts dataset identity evidence such as `sci:doi`, platforms, constellations, and instruments. Missing metadata remains missing rather than being inferred from a familiar collection or asset name.

### Constraint layer

Constraints use three states:

- `pass`: the declared metadata satisfies the requirement
- `fail`: the declared metadata contradicts the requirement
- `unknown`: the catalog does not provide enough information

`unknown` is intentionally distinct from `fail`.

### Verification layer

Availability is item-level evidence. A collection whose temporal and spatial extents overlap a request is still unverified until an item search is performed.

AOI coverage is measured using WGS84 ellipsoidal area. The verifier records both:

- fraction of the AOI covered by an item
- fraction of the item footprint intersected by the AOI

The second value is used as a first-order estimate for windowed asset reads.

### Federation layer

`FederatedScout` composes independent `ScoutEngine` instances. Providers are queried separately, and a failure from one catalog is returned as `ProviderFailure` instead of aborting the entire discovery operation.

Cross-catalog identity is deliberately conservative:

1. `sci:doi` produces an `exact` identity.
2. Matching collection ID plus declared platform, constellation, or instrument metadata produces a `probable` identity.
3. Otherwise identity remains `local` to the catalog and collection.

Both exact and probable matches may be shown as duplicate groups, but only exact groups are marked safe to collapse. This prevents federation from silently treating similar-looking collections as the same scientific product.

### Planning layer

Planning resolves requested measurements against declared asset keys and band metadata. It does not invent aliases when metadata is absent.

When STAC File metadata provides `file:size`, the planner estimates bytes required for the AOI by applying the item intersection fraction. This is an estimate, not a promise about HTTP range behavior or compression layout.

Resampling defaults are semantic:

- masks, QA, classifications, and land cover use nearest-neighbor
- continuous measurements use bilinear interpolation

Provider- or product-specific rules may override these defaults later.

### Provenance layer

A manifest records the request, provider identity when known, catalog, collection, item IDs, selected assets, signing strategy, query, warnings, and Scout version. Replaying a manifest performs a new live item search and reports item-set drift.

A manifest is evidence of how a decision was made; it is not a frozen copy of the remote data.

## Dependency direction

```text
models      registry
  ↑            │
normalize      └── catalog factory
  ↑                  │
constraints      CatalogAdapter
  ↑                  │
verify          ScoutEngine
  ↑               │     │
planning          │     └── FederatedScout
  ↑               │
provenance ───────┘
       ↑
      CLI
```

Remote access is isolated in `catalogs`. Geometry, normalization, identity, constraints, and planning logic remain independently testable.

## Non-goals

The core does not provide:

- a STAC API implementation
- a raster processing engine
- a geocoder
- a general-purpose GIS agent
- an embedding database
- a multi-agent orchestration framework
- heuristic auto-merging of ambiguous cross-provider datasets

Those capabilities can be composed around Scout without becoming core dependencies.
