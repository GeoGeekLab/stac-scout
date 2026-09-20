from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from stac_scout import __version__
from stac_scout.models import (
    CURRENT_MANIFEST_SCHEMA_VERSION,
    AccessPlan,
    AssetSigning,
    AvailabilityProbe,
    CatalogCapabilities,
    DatasetCard,
    ItemEvidence,
    Manifest,
    ScoutRequest,
    SearchCompleteness,
    SearchObservation,
    SearchQuery,
)


class UnsupportedManifestVersionError(ValueError):
    pass


class ManifestIntegrityError(ValueError):
    pass


def _canonical_json(value: BaseModel | dict[str, Any]) -> str:
    payload: Any = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_fingerprint(value: BaseModel | dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def build_manifest(
    request: ScoutRequest,
    *,
    catalog_url: str,
    collection_id: str,
    probe: AvailabilityProbe,
    access_plan: AccessPlan,
    provider_key: str | None = None,
    adapter_type: str | None = None,
    asset_signing: AssetSigning = AssetSigning.NONE,
    catalog_capabilities: CatalogCapabilities | None = None,
    collection_snapshot: DatasetCard | None = None,
    generated_at: datetime | None = None,
    extra_warnings: tuple[str, ...] = (),
) -> Manifest:
    if request.geometry is None:
        raise ValueError("manifest requires resolved request geometry")

    observation = probe.search
    retained_count = len(probe.items)
    if observation.items_retained != retained_count:
        observation = observation.model_copy(
            update={
                "items_observed": max(observation.items_observed, retained_count),
                "items_retained": retained_count,
            }
        )

    query = SearchQuery(
        collections=(collection_id,),
        intersects=request.geometry,
        datetime=f"{request.datetime.start.isoformat()}/{request.datetime.end.isoformat()}",
        max_items=observation.max_items,
    )
    warnings = list(probe.warnings)
    warnings.extend(access_plan.notes)
    warnings.extend(extra_warnings)
    if observation.completeness is SearchCompleteness.UNKNOWN:
        warnings.append("Item Search completeness was not recorded")

    return Manifest(
        scout_version=__version__,
        generated_at=generated_at or datetime.now(UTC),
        request=request,
        request_fingerprint=canonical_fingerprint(request),
        catalog_url=catalog_url,
        collection_id=collection_id,
        provider_key=provider_key,
        adapter_type=adapter_type,
        asset_signing=asset_signing,
        catalog_capabilities=catalog_capabilities,
        collection_snapshot=collection_snapshot,
        collection_fingerprint=(
            canonical_fingerprint(collection_snapshot)
            if collection_snapshot is not None
            else None
        ),
        query=query,
        query_fingerprint=canonical_fingerprint(query),
        observation=observation,
        item_ids=tuple(item.item_id for item in probe.items),
        item_evidence=probe.items,
        access_plan=access_plan,
        asset_keys=access_plan.assets,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def write_manifest(manifest: Manifest, path: Path) -> None:
    path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")


def _legacy_query(
    payload: dict[str, Any],
    request: ScoutRequest,
    collection_id: str,
) -> SearchQuery:
    raw_query = payload.get("query")
    if isinstance(raw_query, dict):
        collections = raw_query.get("collections", [collection_id])
        intersects = raw_query.get("intersects", request.geometry)
        interval = raw_query.get(
            "datetime",
            f"{request.datetime.start.isoformat()}/{request.datetime.end.isoformat()}",
        )
    else:
        collections = [collection_id]
        intersects = request.geometry
        interval = f"{request.datetime.start.isoformat()}/{request.datetime.end.isoformat()}"

    if request.geometry is None or not isinstance(intersects, dict):
        raise ValueError("legacy manifest does not contain resolved query geometry")

    return SearchQuery(
        collections=tuple(str(value) for value in collections),
        intersects=intersects,
        datetime=str(interval),
        max_items=None,
    )


def _migrate_unversioned_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(payload)
    request = ScoutRequest.model_validate(migrated["request"])
    collection_id = str(migrated["collection_id"])
    item_ids = tuple(str(value) for value in migrated.get("item_ids", ()))
    query = _legacy_query(migrated, request, collection_id)
    observation = SearchObservation(
        max_items=None,
        items_observed=len(item_ids),
        items_retained=len(item_ids),
        completeness=SearchCompleteness.UNKNOWN,
        pagination_exhausted=None,
        reason=(
            "legacy unversioned manifest did not record search limit, raw result count, "
            "or pagination completeness"
        ),
    )

    migrated.update(
        {
            "schema_version": CURRENT_MANIFEST_SCHEMA_VERSION,
            "migrated_from_schema_version": "legacy-unversioned",
            "request_fingerprint": canonical_fingerprint(request),
            "adapter_type": None,
            "catalog_capabilities": None,
            "collection_snapshot": None,
            "collection_fingerprint": None,
            "query": query.model_dump(mode="json"),
            "query_fingerprint": canonical_fingerprint(query),
            "observation": observation.model_dump(mode="json"),
            "item_ids": item_ids,
            "item_evidence": [
                ItemEvidence(item_id=item_id).model_dump(mode="json")
                for item_id in item_ids
            ],
            "access_plan": None,
            "migration_warnings": (
                "migrated an unversioned pre-v0.5 manifest; historical search completeness "
                "cannot be proven",
                "legacy manifest did not record the full access plan, Collection snapshot, "
                "or catalog capability evidence",
            ),
        }
    )
    return migrated


def read_manifest(path: Path) -> Manifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("manifest document must be a JSON object")

    schema_version = payload.get("schema_version")
    if schema_version is None:
        payload = _migrate_unversioned_manifest(payload)
    elif schema_version != CURRENT_MANIFEST_SCHEMA_VERSION:
        raise UnsupportedManifestVersionError(
            f"unsupported manifest schema version: {schema_version!r}"
        )

    manifest = Manifest.model_validate(payload)
    if manifest.request_fingerprint != canonical_fingerprint(manifest.request):
        raise ManifestIntegrityError("manifest request fingerprint does not match request")
    if manifest.query_fingerprint != canonical_fingerprint(manifest.query):
        raise ManifestIntegrityError("manifest query fingerprint does not match query")
    if manifest.collection_snapshot is None:
        if manifest.collection_fingerprint is not None:
            raise ManifestIntegrityError(
                "manifest has a Collection fingerprint without a Collection snapshot"
            )
    else:
        expected_collection_fingerprint = canonical_fingerprint(
            manifest.collection_snapshot
        )
        if manifest.collection_fingerprint != expected_collection_fingerprint:
            raise ManifestIntegrityError(
                "manifest Collection fingerprint does not match Collection snapshot"
            )
    return manifest
