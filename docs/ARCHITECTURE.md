# Architecture

STAC Scout separates language-facing intent from data-facing verification. The core package accepts a structured `ScoutRequest`; it does not guess missing geographic facts.

## Boundaries

### Catalog layer

`stac_scout.catalogs` owns remote STAC interaction. `GenericStacAdapter` delegates ordinary STAC operations to `pystac-client`; capability inspection reads the root and conformance documents directly so optional API features are explicit.

Provider-specific behavior belongs behind the `CatalogAdapter` protocol. Signing, authentication, and non-standard catalog structure should not leak into the verification or planning modules.

### Normalization layer

`stac_scout.normalize` converts provider metadata into stable internal models. The normalizer recognizes STAC 1.1 `bands` as well as the older `eo:bands` and `raster:bands` forms.

Normalization is conservative. Missing metadata remains missing rather than being inferred from a familiar collection or asset name.

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

### Planning layer

Planning resolves requested measurements against declared asset keys and band metadata. It does not invent aliases when metadata is absent.

When STAC File metadata provides `file:size`, the planner estimates bytes required for the AOI by applying the item intersection fraction. This is an estimate, not a promise about HTTP range behavior or compression layout.

Resampling defaults are semantic:

- masks, QA, classifications, and land cover use nearest-neighbor
- continuous measurements use bilinear interpolation

Provider- or product-specific rules may override these defaults later.

### Provenance layer

A manifest records the request, catalog, collection, item IDs, selected assets, query, warnings, and Scout version. Replaying a manifest performs a new live item search and reports item-set drift.

A manifest is evidence of how a decision was made; it is not a frozen copy of the remote data.

## Dependency direction

```text
models
  ↑
normalize   constraints   verify
     \         |         /
      \        |        /
       discovery / planning
              ↑
           scout.py
              ↑
             CLI
```

Remote access is isolated in `catalogs`. Pure geometry, normalization, constraints, and planning functions remain independently testable.

## Non-goals

The core does not provide:

- a STAC API implementation
- a raster processing engine
- a geocoder
- a general-purpose GIS agent
- an embedding database
- a multi-agent orchestration framework

Those capabilities can be composed around Scout without becoming core dependencies.
