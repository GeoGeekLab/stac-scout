from __future__ import annotations

from typing import Any

from stac_scout.constraints import evaluate_plan_constraints
from stac_scout.models import AccessPlan, AssetChoice, AvailabilityProbe, DataType, ScoutRequest

from .assets import select_asset_choices
from .volume import estimate_asset_bytes

_CATEGORICAL_MEASUREMENTS = {
    "classification",
    "cloud_mask",
    "fmask",
    "land_cover",
    "mask",
    "pixel_qa",
    "qa",
    "qa60",
    "quality",
    "scl",
}
_CONTINUOUS_MEASUREMENTS = {
    "blue",
    "cirrus",
    "coastal",
    "elevation",
    "green",
    "hh",
    "hv",
    "lwir11",
    "lwir12",
    "nir",
    "nir08",
    "nir09",
    "pan",
    "red",
    "rededge",
    "swir16",
    "swir22",
    "temperature",
    "vh",
    "vv",
    "yellow",
}


def _all_band_definitions(asset: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    bands: list[dict[str, Any]] = []
    for key in ("bands", "eo:bands", "raster:bands"):
        value = asset.get(key)
        if isinstance(value, list):
            bands.extend(entry for entry in value if isinstance(entry, dict))
    return tuple(bands)


def _normalized_name(value: str) -> str:
    return value.casefold().replace("-", "_").replace(" ", "_")


def resampling_for(measurement: str) -> str | None:
    """Return a conservative name-only resampling default.

    Rich planning also inspects selected asset metadata before using this fallback.
    Unknown semantics intentionally remain unresolved.
    """

    normalized = _normalized_name(measurement)
    if normalized in _CATEGORICAL_MEASUREMENTS:
        return "nearest"
    if normalized in _CONTINUOUS_MEASUREMENTS:
        return "bilinear"
    return None


def _asset_evidence(
    items: list[dict[str, Any]],
    asset_key: str,
) -> tuple[set[str], tuple[dict[str, Any], ...]]:
    roles: set[str] = set()
    bands: list[dict[str, Any]] = []

    for item in items:
        assets = item.get("assets")
        if not isinstance(assets, dict):
            continue
        asset = assets.get(asset_key)
        if not isinstance(asset, dict):
            continue

        raw_roles = asset.get("roles")
        if isinstance(raw_roles, list):
            roles.update(str(role).casefold() for role in raw_roles if isinstance(role, str))
        bands.extend(_all_band_definitions(asset))

    return roles, tuple(bands)


def _resampling_decision(
    choice: AssetChoice,
    items: list[dict[str, Any]],
    data_type: DataType,
) -> tuple[str | None, str | None]:
    roles, bands = _asset_evidence(items, choice.asset_key)

    if roles & {"mask", "quality"}:
        return ("nearest", "selected asset has mask/quality role")

    for band in bands:
        classes = band.get("classification:classes")
        if isinstance(classes, list):
            return ("nearest", "selected band declares classification:classes")

    names = {_normalized_name(choice.measurement)}
    for band in bands:
        for key in ("name", "common_name"):
            value = band.get(key)
            if isinstance(value, str):
                names.add(_normalized_name(value))

    if names & _CATEGORICAL_MEASUREMENTS:
        return ("nearest", "known categorical measurement semantics")
    if data_type is DataType.LAND_COVER:
        return ("nearest", "land-cover data type is categorical")
    if names & _CONTINUOUS_MEASUREMENTS:
        return ("bilinear", "known continuous measurement semantics")
    if data_type is DataType.ELEVATION:
        return ("bilinear", "elevation data type is continuous")

    return (None, None)


def build_access_plan(
    request: ScoutRequest,
    items: list[dict[str, Any]],
    probe: AvailabilityProbe,
    *,
    output_crs: str | None = None,
) -> tuple[AccessPlan, tuple[str, ...]]:
    if output_crs is not None:
        if request.target_crs is None:
            raise ValueError("set target_crs on ScoutRequest instead of passing output_crs")
        if output_crs.casefold() != request.target_crs.casefold():
            raise ValueError("output_crs conflicts with request.target_crs")

    choices, missing, ambiguous = select_asset_choices(
        items,
        request.required_measurements,
        max_source_resolution_m=request.max_source_resolution_m,
    )

    resolved_choices: list[AssetChoice] = []
    for choice in choices:
        method, basis = _resampling_decision(choice, items, request.data_type)
        resolved_choices.append(
            choice.model_copy(
                update={
                    "resampling": method,
                    "resampling_basis": basis,
                }
            )
        )

    final_choices = tuple(resolved_choices)
    asset_keys = tuple(dict.fromkeys(choice.asset_key for choice in final_choices))
    estimated_bytes = estimate_asset_bytes(items, asset_keys, probe=probe, windowed=True)
    constraints = evaluate_plan_constraints(
        estimated_bytes,
        request,
        asset_choices=final_choices,
        missing_measurements=missing,
        ambiguous_measurements=ambiguous,
    )
    resampling = {
        choice.measurement: choice.resampling
        for choice in final_choices
        if choice.resampling is not None
    }

    notes: list[str] = []
    if missing:
        notes.append(f"unresolved measurements with no matching asset: {', '.join(missing)}")
    if ambiguous:
        ambiguous_names = ", ".join(ambiguous)
        notes.append(
            f"ambiguous asset selection; no lexicographic fallback used for: "
            f"{ambiguous_names}"
        )

    incomplete = tuple(
        choice.measurement for choice in final_choices if not choice.item_coverage_complete
    )
    if incomplete:
        notes.append(
            "selected asset key is not present on every inspected Item for: "
            + ", ".join(incomplete)
        )

    unknown_resampling = tuple(
        choice.measurement for choice in final_choices if choice.resampling is None
    )
    if unknown_resampling:
        notes.append(
            "resampling semantics are unknown; no default was invented for: "
            + ", ".join(unknown_resampling)
        )

    if estimated_bytes is None and asset_keys:
        notes.append("asset sizes are not declared; transfer size is unknown")

    unresolved = tuple(dict.fromkeys((*missing, *ambiguous)))
    return (
        AccessPlan(
            strategy="windowed-assets",
            assets=asset_keys,
            asset_choices=final_choices,
            estimated_bytes=estimated_bytes,
            output_crs=request.target_crs,
            output_resolution=request.target_resolution_m,
            resampling=resampling,
            constraints=constraints,
            notes=tuple(notes),
        ),
        unresolved,
    )
