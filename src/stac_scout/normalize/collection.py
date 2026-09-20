from __future__ import annotations

from datetime import datetime
from typing import Any

from stac_scout.models import DatasetCard, DataType

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
    extent = raw.get("extent")
    if not isinstance(extent, dict):
        return None
    spatial = extent.get("spatial")
    if not isinstance(spatial, dict):
        return None
    boxes = spatial.get("bbox")
    if boxes is None:
        return None
    if not isinstance(boxes, list):
        raise ValueError("Collection spatial bbox metadata must be a list")
    if not boxes:
        return None

    valid_boxes: list[tuple[float, float, float, float]] = []
    for box in boxes:
        if not isinstance(box, list) or len(box) < 4:
            raise ValueError("Collection spatial bbox entry must contain four coordinates")
        values = box[:4]
        if any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in values):
            raise ValueError("Collection spatial bbox coordinates must be numeric")
        west, south, east, north = (float(value) for value in values)
        valid_boxes.append((west, south, east, north))

    return (
        min(box[0] for box in valid_boxes),
        min(box[1] for box in valid_boxes),
        max(box[2] for box in valid_boxes),
        max(box[3] for box in valid_boxes),
    )


def _temporal_extent(raw: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    extent = raw.get("extent")
    if not isinstance(extent, dict):
        return (None, None)
    temporal = extent.get("temporal")
    if not isinstance(temporal, dict):
        return (None, None)
    intervals = temporal.get("interval")
    if not isinstance(intervals, list):
        return (None, None)

    parsed: list[tuple[datetime | None, datetime | None]] = []
    for interval in intervals:
        if not isinstance(interval, list):
            continue
        raw_start = interval[0] if len(interval) > 0 else None
        raw_end = interval[1] if len(interval) > 1 else None
        start = _parse_datetime(raw_start)
        end = _parse_datetime(raw_end)
        if raw_start is not None and start is None:
            continue
        if raw_end is not None and end is None:
            continue
        parsed.append((start, end))

    if not parsed:
        return (None, None)

    starts = [start for start, _ in parsed]
    ends = [end for _, end in parsed]
    overall_start = (
        None
        if any(value is None for value in starts)
        else min(value for value in starts if value is not None)
    )
    overall_end = (
        None
        if any(value is None for value in ends)
        else max(value for value in ends if value is not None)
    )
    return (overall_start, overall_end)


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
