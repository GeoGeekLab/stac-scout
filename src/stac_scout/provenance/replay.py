from __future__ import annotations

from dataclasses import dataclass

from stac_scout.catalogs import CatalogAdapter
from stac_scout.models import AvailabilityProbe, Manifest
from stac_scout.verify import probe_items


@dataclass(frozen=True, slots=True)
class ReplayResult:
    probe: AvailabilityProbe
    retained_item_ids: tuple[str, ...]
    missing_item_ids: tuple[str, ...]
    new_item_ids: tuple[str, ...]


def replay_manifest(
    manifest: Manifest,
    adapter: CatalogAdapter,
    *,
    max_items: int = 100,
) -> ReplayResult:
    geometry = manifest.request.geometry
    if geometry is None:
        raise ValueError("manifest request has no geometry")

    items = adapter.search_items(
        manifest.request,
        manifest.collection_id,
        max_items=max_items,
    )
    probe = probe_items(items, geometry)
    previous = set(manifest.item_ids)
    current = {item.item_id for item in probe.items}
    return ReplayResult(
        probe=probe,
        retained_item_ids=tuple(sorted(previous & current)),
        missing_item_ids=tuple(sorted(previous - current)),
        new_item_ids=tuple(sorted(current - previous)),
    )
