# Manifest and replay contract

STAC Scout manifests are evidence records, not frozen copies of remote data.

## Schema version

Current manifest schema: `1.0`.

Every newly written manifest includes `schema_version`. Readers accept the current schema and
perform one conservative compatibility migration for unversioned manifests written before the
v0.5 hardening work.

Unversioned legacy manifests did not record search limits, raw result counts, pagination
completeness, full access-plan evidence, Collection snapshots, or catalog capability evidence.
When such a manifest is read:

- it is migrated in memory to schema `1.0`;
- `migrated_from_schema_version` is set to `legacy-unversioned`;
- historical Item Search completeness is `unknown`;
- missing provenance is not invented;
- migration warnings remain attached to the manifest.

Unknown future schema versions are rejected until an explicit migration is implemented. The
reader does not silently reinterpret a future contract.

## Canonical evidence

Schema `1.0` records:

- the structured `ScoutRequest` and its canonical SHA-256 fingerprint;
- provider key, adapter type, catalog URL, signing policy, and catalog capability snapshot when
  available;
- the normalized Collection snapshot and canonical fingerprint when available;
- a typed STAC Item Search query and canonical fingerprint;
- the search limit, raw Item count, retained Item count, and completeness state;
- retained Item evidence;
- the full access plan, including asset choices, resampling, output CRS/resolution, and volume
  estimate;
- warnings and assumptions.

Canonical fingerprints use JSON with sorted object keys and stable separators. They identify the
recorded decision inputs; they are not content-addressed hashes of remote raster assets.

## Completeness states

`complete`
: Item Search returned fewer Items than the configured limit. Scout exhausted the observed result
  stream before reaching its cap.

`capped`
: Item Search returned exactly the configured limit. Scout cannot prove whether additional
  matching Items exist.

`unknown`
: The search limit or pagination evidence was not recorded, as with legacy manifests or manually
  constructed probes.

Reaching a result cap is not proof that more Items exist. It is proof that completeness was not
established.

## Replay semantics

Replay re-runs the original request and Collection through the same deterministic verification
path. Unless the caller overrides it, replay uses the search limit recorded in the manifest.

Item-set differences are classified by what can actually be proven:

| Original | Replay | Missing original Item | Newly observed replay Item |
| --- | --- | --- | --- |
| complete | complete | confirmed missing | confirmed new |
| complete | capped/unknown | unresolved | confirmed new |
| capped/unknown | complete | confirmed missing | unresolved |
| capped/unknown | capped/unknown | unresolved | unresolved |

Thus a provider changing the ordering of two capped 100-Item samples cannot create false
confirmed drift.

The compatibility properties `ReplayResult.missing_item_ids` and
`ReplayResult.new_item_ids` expose confirmed differences only. New code should prefer the
explicit `confirmed_*` and `unresolved_*` fields.

## What replay does not prove

Replay does not prove that the underlying asset bytes are unchanged. It compares current
decision/query evidence and Item identities. Asset checksums or immutable object-version
identifiers may be added by future schema versions when providers expose trustworthy evidence.
