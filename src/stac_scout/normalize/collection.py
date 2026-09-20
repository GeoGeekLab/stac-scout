from __future__ import annotations

from datetime import datetime
from typing import Any

from stac_scout.models import DataType, DatasetCard

from .assets import normalize_asset
from .bands import band_definitions, normalize_band


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


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
    if isinstance(summary, (int, float)) and not isinstance(summary, bool):
        values.append(float(summary))
    elif isinstance(summary, list):
        values.extend(
            float(value)
            for value in summary
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        )

    item_assets = raw.get("item_assets", {})
    if isinstance(item_assets, dict):
        for asset in item_assets.values():
            if (
                isinstance(asset, dict)
                and isinstance(asset.get("gsd"), (int, float))
                and not isinstance(asset.get("gsd"), bool)
            ):
                values.append(float(asset["gsd"]))

    return min(values) if values else None


def _string_values(raw: dict[str, Any], key: str) -> tuple[str, ...]:
    value = raw.get(key)
    if value is None:
        summaries = raw.get("summaries", {})
        value = summaries.get(key) if isinstance(summaries, dict) else None

    if isinstance(value, str):
        return (value,)
    if isinstance(value, list):
        return tuple(str(entry) for entry in value if isinstance(entry, str))
    return ()


def _modality_evidence(mapping: dict[str, Any]) -> set[DataType]:
    evidence: set[DataType] = set()
    keys = {key.casefold() for key in mapping if isinstance(key, str)}
    if any(key.startswith("sar:") for key in keys):
        evidence.add(DataType.SAR)
    if any(key.startswith("eo:") for key in keys):
        evidence.add(DataType.OPTICAL)
    return evidence


def _data_type(raw: dict[str, Any]) -> DataType | None:
    evidence = _modality_evidence(raw)

    extensions = raw.get("stac_extensions")
    if isinstance(extensions, list):
        for extension in extensions:
            if not isinstance(extension, str):
                continue
            normalized = extension.casefold()
            if "/sar/" in normalized:
                evidence.add(DataType.SAR)
            if "/eo/" in normalized:
                evidence.add(DataType.OPTICAL)

    summaries = raw.get("summaries")
    if isinstance(summaries, dict):
        evidence.update(_modality_evidence(summaries))

    item_assets = raw.get("item_assets")
    if isinstance(item_assets, dict):
        for asset in item_assets.values():
            if isinstance(asset, dict):
                evidence.update(_modality_evidence(asset))

    if len(evidence) == 1:
        return next(iter(evidence))
    return None


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
    doi = raw.get("sci:doi")

    return DatasetCard(
        catalog_url=catalog_url,
        collection_id=str(raw["id"]),
        title=raw.get("title"),
        description=raw.get("description"),
        doi=doi if isinstance(doi, str) else None,
        data_type=_data_type(raw),
        providers=providers,
        platforms=_string_values(raw, "platform"),
        constellations=_string_values(raw, "constellation"),
        instruments=_string_values(raw, "instruments"),
        license=raw.get("license"),
        spatial_extent=_spatial_extent(raw),
        temporal_start=start,
        temporal_end=end,
        spatial_resolution_m=_resolution(raw),
        bands=bands,
        assets=assets,
        source=raw,
    )
