from __future__ import annotations

from datetime import datetime
from typing import Any

from stac_scout.models import DatasetCard

from .assets import normalize_asset
from .bands import band_definitions, normalize_band


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _spatial_extent(raw: dict[str, Any]) -> tuple[float, float, float, float] | None:
    boxes = raw.get("extent", {}).get("spatial", {}).get("bbox", [])
    if not boxes or not isinstance(boxes[0], list) or len(boxes[0]) < 4:
        return None
    west, south, east, north = boxes[0][:4]
    return (float(west), float(south), float(east), float(north))


def _temporal_extent(raw: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    intervals = raw.get("extent", {}).get("temporal", {}).get("interval", [])
    if not intervals or not isinstance(intervals[0], list):
        return (None, None)
    start = intervals[0][0] if len(intervals[0]) > 0 else None
    end = intervals[0][1] if len(intervals[0]) > 1 else None
    return (_parse_datetime(start), _parse_datetime(end))


def _resolution(raw: dict[str, Any]) -> float | None:
    values: list[float] = []
    summary = raw.get("summaries", {}).get("gsd")
    if isinstance(summary, (int, float)):
        values.append(float(summary))
    elif isinstance(summary, list):
        values.extend(float(value) for value in summary if isinstance(value, (int, float)))

    item_assets = raw.get("item_assets", {})
    if isinstance(item_assets, dict):
        for asset in item_assets.values():
            if isinstance(asset, dict) and isinstance(asset.get("gsd"), (int, float)):
                values.append(float(asset["gsd"]))

    return min(values) if values else None


def normalize_collection(raw: dict[str, Any], catalog_url: str) -> DatasetCard:
    start, end = _temporal_extent(raw)
    providers = tuple(
        provider["name"]
        for provider in raw.get("providers", [])
        if isinstance(provider, dict) and isinstance(provider.get("name"), str)
    )

    item_assets = raw.get("item_assets", {})
    assets = (
        tuple(
            normalize_asset(key, value)
            for key, value in item_assets.items()
            if isinstance(value, dict)
        )
        if isinstance(item_assets, dict)
        else ()
    )

    summary_bands = raw.get("summaries", {})
    bands = tuple(normalize_band(band) for band in band_definitions(summary_bands))

    return DatasetCard(
        catalog_url=catalog_url,
        collection_id=str(raw["id"]),
        title=raw.get("title"),
        description=raw.get("description"),
        providers=providers,
        license=raw.get("license"),
        spatial_extent=_spatial_extent(raw),
        temporal_start=start,
        temporal_end=end,
        spatial_resolution_m=_resolution(raw),
        bands=bands,
        assets=assets,
        source=raw,
    )
