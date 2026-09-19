---
name: stac-scout
description: Select and verify geospatial datasets from STAC catalogs using live metadata and item evidence.
license: MIT
---

# STAC Scout

Use this skill when the user needs help choosing, verifying, comparing, or planning access to STAC-hosted geospatial datasets.

## Rules

1. Convert the request into explicit spatial, temporal, scientific, access, and volume constraints.
2. Keep missing or ambiguous natural-language constraints in `unresolved`; never invent coordinates or dates.
3. Inspect catalog capabilities before relying on optional STAC API features.
4. Treat collection metadata as candidate evidence, not proof of item availability.
5. Probe items for the requested AOI and time range before stating that data exists.
6. Inspect asset and band metadata before naming required assets.
7. Distinguish `false` from `unknown` when metadata is incomplete.
8. When searching multiple providers, keep provider failures visible rather than silently dropping them.
9. Treat DOI-backed dataset identity as stronger than title or collection-name similarity.
10. Never silently merge probable cross-provider duplicates.
11. Preserve provider-specific access requirements such as Planetary Computer asset signing.
12. Treat provider health as operational evidence, never as scientific ranking evidence.
13. Report caveats that materially affect scientific use or access cost.
14. Prefer reproducible queries and manifests over prose-only answers.

Never infer what can be inspected.
