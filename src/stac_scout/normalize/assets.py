from __future__ import annotations

from typing import Any

from stac_scout.models import AssetInfo

from .bands import band_definitions, normalize_band


def normalize_asset(key: str, raw: dict[str, Any]) -> AssetInfo:
    size = raw.get("file:size")
    size_bytes = (
        size
        if isinstance(size, int) and not isinstance(size, bool) and size >= 0
        else None
    )
    gsd = raw.get("gsd")
    gsd_m = (
        float(gsd)
        if isinstance(gsd, (int, float)) and not isinstance(gsd, bool) and gsd > 0
        else None
    )
    roles_value = raw.get("roles")
    roles = roles_value if isinstance(roles_value, list) else []
    bands = tuple(normalize_band(band) for band in band_definitions(raw))
    return AssetInfo(
        key=key,
        href=raw.get("href"),
        media_type=raw.get("type"),
        roles=tuple(str(role) for role in roles),
        title=raw.get("title"),
        bands=bands,
        size_bytes=size_bytes,
        gsd_m=gsd_m,
    )
