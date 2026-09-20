from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from stac_scout import __version__
from stac_scout.models import (
    AccessPlan,
    AssetMetadataSnapshot,
    AssetSigning,
    AvailabilityProbe,
    CatalogCapabilities,
    CollectionSnapshot,
    DatasetCard,
    Manifest,
    ScoutRequest,
    SearchCompleteness,
    SearchObservation,
)
from stac_scout.normalize.assets import normalize_asset

MANIFEST_SCHEMA_VERSION = 1


def _collection_snapshot(card: DatasetCard) -> CollectionSnapshot:
    return CollectionSnapshot(
        collection_id=card.collection_id,
        title=card.title,
        doi=card.doi,
        data_type=card.data_type,
        providers=card.providers,
        platforms=card.platforms,
        constellations=card.constellations,
        instruments=card.instruments,
        license=card.license,
        spatial_extent=card.spatial_extent,
        temporal_start=card.temporal_start,
        temporal_end=card.temporal_end,
        spatial_resolution_m=card.spatial_resolution_m,
        measurements=tuple(sorted(card.measurements)),
    )


def _fingerprint(snapshot: CollectionSnapshot) -> str:
    payload = json.dumps(
        snapshot.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _asset_metadata(
    items: Sequence[dict[str, Any]],
    selected_asset_keys: Sequence[str],
) -> tuple[AssetMetadataSnapshot, ...]:
    selected = set(selected_asset_keys)
    snapshots: list[AssetMetadataSnapshot] = []

    for item in items:
        item_id = str(item.get("id", "<unknown>"))
        raw_assets = item.get("assets")
        if not isinstance(raw_assets, dict):
            continue

        for asset_key in sorted(selected):
            raw_asset = raw_assets.get(asset_key)
            if not isinstance(raw_asset, dict):
                continue
            normalized = normalize_asset(asset_key, raw_asset)
            snapshots.append(
                AssetMetadataSnapshot(
                    item_id=item_id,
                    asset_key=asset_key,
                    media_type=normalized.media_type,
                    roles=normalized.roles,
                    title=normalized.title,
                    bands=normalized.bands,
                    size_bytes=normalized.size_bytes,
                    gsd_m=normalized.gsd_m,
                )
            )

    snapshots.sort(key=lambda snapshot: (snapshot.item_id, snapshot.asset_key))
    return tuple(snapshots)


def _unknown_search(item_count: int) -> SearchObservation:
    return SearchObservation(
        max_items=None,
        returned_items=item_count,
        accepted_items=item_count,
        completeness=SearchCompleteness.UNKNOWN,
        pagination_mode="unknown",
        ordering="provider-default",
    )


def build_manifest(
    request: ScoutRequest,
    *,
    catalog_url: str,
    collection_id: str,
    probe: AvailabilityProbe,
    access_plan: AccessPlan,
    provider_key: str | None = None,
    asset_signing: AssetSigning = AssetSigning.NONE,
    generated_at: datetime | None = None,
    search: SearchObservation | None = None,
    collection: DatasetCard | None = None,
    catalog_capabilities: CatalogCapabilities | None = None,
    items: Sequence[dict[str, Any]] = (),
    additional_warnings: Sequence[str] = (),
) -> Manifest:
    search_observation = search or _unknown_search(len(probe.items))
    query = {
        "collections": [collection_id],
        "datetime": f"{request.datetime.start.isoformat()}/{request.datetime.end.isoformat()}",
        "intersects": request.geometry,
        "max_items": search_observation.max_items,
    }

    warnings = list(probe.warnings)
    warnings.extend(access_plan.notes)
    warnings.extend(additional_warnings)
    if search is None:
        warnings.append(
            "search completeness was not supplied when the manifest was built; "
            "replay drift is conservative"
        )

    collection_snapshot = _collection_snapshot(collection) if collection is not None else None

    return Manifest(
        schema_version=MANIFEST_SCHEMA_VERSION,
        scout_version=__version__,
        generated_at=generated_at or datetime.now(UTC),
        request=request,
        catalog_url=catalog_url,
        collection_id=collection_id,
        provider_key=provider_key,
        asset_signing=asset_signing,
        catalog_capabilities=catalog_capabilities,
        collection_snapshot=collection_snapshot,
        collection_fingerprint_sha256=(
            _fingerprint(collection_snapshot) if collection_snapshot is not None else None
        ),
        query=query,
        search=search_observation,
        access_plan=access_plan,
        item_ids=tuple(item.item_id for item in probe.items),
        asset_keys=access_plan.assets,
        asset_metadata=_asset_metadata(items, access_plan.assets),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def write_manifest(manifest: Manifest, path: Path) -> None:
    payload = json.dumps(
        manifest.model_dump(mode="json"),
        indent=2,
        sort_keys=True,
    )
    path.write_text(payload + "\n", encoding="utf-8")


def _migrate_unversioned_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(payload)
    item_ids = migrated.get("item_ids")
    item_count = len(item_ids) if isinstance(item_ids, list) else 0
    warnings = migrated.get("warnings")
    warning_list = list(warnings) if isinstance(warnings, list) else []
    warning_list.append(
        "legacy unversioned manifest migrated to schema v1; "
        "historical search completeness is unknown"
    )

    migrated["schema_version"] = MANIFEST_SCHEMA_VERSION
    migrated["catalog_capabilities"] = None
    migrated["collection_snapshot"] = None
    migrated["collection_fingerprint_sha256"] = None
    migrated["search"] = {
        "max_items": None,
        "returned_items": item_count,
        "accepted_items": item_count,
        "completeness": SearchCompleteness.UNKNOWN.value,
        "pagination_mode": "unknown",
        "ordering": "provider-default",
    }
    migrated["access_plan"] = None
    migrated["asset_metadata"] = []
    migrated["warnings"] = warning_list
    return migrated


def read_manifest(path: Path) -> Manifest:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("manifest root must be a JSON object")

    schema_version = raw.get("schema_version")
    if schema_version is None:
        raw = _migrate_unversioned_manifest(raw)
    elif schema_version != MANIFEST_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported manifest schema version: {schema_version}; "
            f"supported version is {MANIFEST_SCHEMA_VERSION}"
        )

    return Manifest.model_validate(raw)
