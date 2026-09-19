from __future__ import annotations

from typing import Any

from stac_scout.models import AccessPlan, AvailabilityProbe, ScoutRequest

from .assets import select_asset_keys
from .volume import estimate_asset_bytes

_NEAREST = {"classification", "cloud_mask", "mask", "qa", "quality", "land_cover"}


def resampling_for(measurement: str) -> str:
    return "nearest" if measurement.casefold() in _NEAREST else "bilinear"


def build_access_plan(
    request: ScoutRequest,
    items: list[dict[str, Any]],
    probe: AvailabilityProbe,
    *,
    output_crs: str | None = None,
) -> tuple[AccessPlan, tuple[str, ...]]:
    asset_keys, missing = select_asset_keys(items, request.required_measurements)
    estimated_bytes = estimate_asset_bytes(items, asset_keys, probe=probe, windowed=True)
    resampling = {
        measurement: resampling_for(measurement)
        for measurement in request.required_measurements
        if measurement not in missing
    }
    notes: list[str] = []
    if missing:
        notes.append(f"unresolved measurements: {', '.join(missing)}")
    if estimated_bytes is None and asset_keys:
        notes.append("asset sizes are not declared; transfer size is unknown")

    return (
        AccessPlan(
            strategy="windowed-assets",
            assets=asset_keys,
            estimated_bytes=estimated_bytes,
            output_crs=output_crs,
            output_resolution=request.max_spatial_resolution_m,
            resampling=resampling,
            notes=tuple(notes),
        ),
        missing,
    )
