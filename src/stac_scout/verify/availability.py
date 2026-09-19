from __future__ import annotations

from datetime import datetime
from typing import Any

from stac_scout.models import AvailabilityProbe, ItemEvidence, VerificationStatus

from .coverage import coverage_metrics


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def probe_items(
    items: list[dict[str, Any]],
    aoi_geojson: dict[str, Any],
) -> AvailabilityProbe:
    if not items:
        return AvailabilityProbe(
            status=VerificationStatus.VERIFIED_EMPTY,
            items_checked=0,
        )

    evidence: list[ItemEvidence] = []
    warnings: list[str] = []
    for item in items:
        coverage: float | None = None
        item_fraction: float | None = None
        geometry = item.get("geometry")
        if isinstance(geometry, dict):
            try:
                coverage, item_fraction = coverage_metrics(aoi_geojson, geometry)
            except (TypeError, ValueError):
                warnings.append(f"could not measure coverage for item {item.get('id', '<unknown>')}")

        properties = item.get("properties", {})
        cloud_cover = properties.get("eo:cloud_cover")
        if not isinstance(cloud_cover, (int, float)):
            cloud_cover = None

        assets = item.get("assets", {})
        asset_keys = tuple(sorted(assets)) if isinstance(assets, dict) else ()
        evidence.append(
            ItemEvidence(
                item_id=str(item.get("id", "")),
                datetime=_parse_datetime(properties.get("datetime")),
                coverage_ratio=coverage,
                item_fraction_read=item_fraction,
                cloud_cover=float(cloud_cover) if cloud_cover is not None else None,
                asset_keys=asset_keys,
            )
        )

    max_coverage = max(
        (entry.coverage_ratio for entry in evidence if entry.coverage_ratio is not None),
        default=None,
    )
    return AvailabilityProbe(
        status=VerificationStatus.VERIFIED_AVAILABLE,
        items_checked=len(evidence),
        max_coverage_ratio=max_coverage,
        items=tuple(evidence),
        warnings=tuple(dict.fromkeys(warnings)),
    )
