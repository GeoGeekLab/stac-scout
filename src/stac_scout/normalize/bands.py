from __future__ import annotations

from typing import Any

from stac_scout.models import BandInfo


def normalize_band(raw: dict[str, Any]) -> BandInfo:
    return BandInfo(
        name=raw.get("name"),
        common_name=raw.get("common_name"),
        description=raw.get("description"),
        center_wavelength=raw.get("center_wavelength"),
        full_width_half_max=raw.get("full_width_half_max"),
        unit=raw.get("unit"),
        scale=raw.get("scale"),
        offset=raw.get("offset"),
        nodata=raw.get("nodata"),
    )


def band_definitions(raw: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    for key in ("bands", "eo:bands", "raster:bands"):
        value = raw.get(key)
        if isinstance(value, list):
            return tuple(entry for entry in value if isinstance(entry, dict))
    return ()
