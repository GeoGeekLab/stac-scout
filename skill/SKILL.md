---
name: stac-scout
description: Select and verify geospatial datasets from STAC catalogs using live metadata and item evidence.
license: MIT
---

# STAC Scout

Use this skill when the user needs help choosing, verifying, comparing, or planning access to STAC-hosted geospatial datasets.

## Rules

1. Convert the request into explicit spatial, temporal, scientific, access, and volume constraints.
2. Inspect catalog capabilities before relying on optional STAC API features.
3. Treat collection metadata as candidate evidence, not proof of item availability.
4. Probe items for the requested AOI and time range before stating that data exists.
5. Inspect asset and band metadata before naming required assets.
6. Distinguish `false` from `unknown` when metadata is incomplete.
7. When searching multiple providers, keep provider failures visible rather than silently dropping them.
8. Treat DOI-backed dataset identity as stronger than title or collection-name similarity.
9. Never silently merge probable cross-provider duplicates.
10. Preserve provider-specific access requirements such as Planetary Computer asset signing.
11. Report caveats that materially affect scientific use or access cost.
12. Prefer reproducible queries and manifests over prose-only answers.

Never infer what can be inspected.
