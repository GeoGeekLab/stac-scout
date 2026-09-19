---
name: stac-scout
description: Derive, select, and verify geospatial data requirements across STAC catalogs using explicit task rules and live evidence.
license: MIT
---

# STAC Scout

Use this skill when the user needs help deciding what geospatial data a task requires, then choosing, verifying, comparing, or planning access to STAC-hosted datasets.

## Rules

1. Convert natural language into explicit spatial, temporal, scientific, access, and volume constraints.
2. If the goal clearly maps to a supported task archetype, set `task_type`; do not invent spectral measurements in the language-model layer.
3. Apply the deterministic task registry to derive required and preferred data needs.
4. Preserve explicit user constraints when they differ from task defaults and report the conflict.
5. Never invent comparison windows for before/after tasks; return them as follow-up requirements.
6. Inspect catalog capabilities before relying on optional STAC API features.
7. Treat collection metadata as candidate evidence, not proof of item availability.
8. Probe items for the requested AOI and time range before stating that data exists.
9. Inspect asset and band metadata before naming required assets.
10. Distinguish `false` from `unknown` when metadata is incomplete.
11. Keep provider failures visible during federation.
12. Never silently merge probable cross-provider duplicates.
13. Preserve provider-specific access requirements such as Planetary Computer asset signing.
14. Treat provider health as operational evidence, never as scientific ranking evidence.
15. Prefer reproducible queries, rule evidence, and manifests over prose-only answers.

Never infer what can be inspected.
