from __future__ import annotations

from typing import Any

from stac_scout.normalize.bands import band_definitions


def _asset_measurements(key: str, asset: dict[str, Any]) -> set[str]:
    values = {key.casefold()}
    for band in band_definitions(asset):
        name = band.get("name")
        common_name = band.get("common_name")
        if isinstance(name, str):
            values.add(name.casefold())
        if isinstance(common_name, str):
            values.add(common_name.casefold())
    return values


def select_asset_keys(
    items: list[dict[str, Any]],
    measurements: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if not measurements:
        return ((), ())

    candidates: dict[str, set[str]] = {}
    for item in items:
        assets = item.get("assets", {})
        if not isinstance(assets, dict):
            continue
        for key, asset in assets.items():
            if isinstance(asset, dict):
                candidates.setdefault(key, set()).update(_asset_measurements(key, asset))

    selected: list[str] = []
    missing: list[str] = []
    for measurement in measurements:
        target = measurement.casefold()
        matches = sorted(key for key, values in candidates.items() if target in values)
        if matches:
            selected.append(matches[0])
        else:
            missing.append(measurement)

    return (tuple(dict.fromkeys(selected)), tuple(missing))
