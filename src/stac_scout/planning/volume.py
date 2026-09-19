from __future__ import annotations

from typing import Any

from stac_scout.models import AvailabilityProbe


def _file_size(asset: dict[str, Any]) -> int | None:
    size = asset.get("file:size")
    return size if isinstance(size, int) and size >= 0 else None


def estimate_asset_bytes(
    items: list[dict[str, Any]],
    asset_keys: tuple[str, ...],
    *,
    probe: AvailabilityProbe | None = None,
    windowed: bool = True,
) -> int | None:
    fractions = {
        item.item_id: item.item_fraction_read
        for item in probe.items
        if item.item_fraction_read is not None
    } if probe is not None else {}

    total = 0.0
    observed = False
    for item in items:
        assets = item.get("assets", {})
        if not isinstance(assets, dict):
            continue
        fraction = fractions.get(str(item.get("id")), 1.0) if windowed else 1.0
        for key in asset_keys:
            asset = assets.get(key)
            if not isinstance(asset, dict):
                continue
            size = _file_size(asset)
            if size is None:
                continue
            observed = True
            total += size * fraction

    return round(total) if observed else None
