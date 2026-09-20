from __future__ import annotations

from dataclasses import dataclass

from stac_scout.catalogs import CatalogAdapter
from stac_scout.models import (
    AvailabilityProbe,
    Manifest,
    SearchCompleteness,
    SearchObservation,
)


@dataclass(frozen=True, slots=True)
class ReplayResult:
    probe: AvailabilityProbe
    previous_observation: SearchObservation
    current_observation: SearchObservation
    retained_item_ids: tuple[str, ...]
    confirmed_missing_item_ids: tuple[str, ...]
    confirmed_new_item_ids: tuple[str, ...]
    unresolved_missing_item_ids: tuple[str, ...]
    unresolved_new_item_ids: tuple[str, ...]
    comparison_complete: bool
    warnings: tuple[str, ...] = ()

    @property
    def missing_item_ids(self) -> tuple[str, ...]:
        """Backward-compatible alias for confirmed missing Items only."""
        return self.confirmed_missing_item_ids

    @property
    def new_item_ids(self) -> tuple[str, ...]:
        """Backward-compatible alias for confirmed new Items only."""
        return self.confirmed_new_item_ids


def replay_manifest(
    manifest: Manifest,
    adapter: CatalogAdapter,
    *,
    max_items: int | None = None,
) -> ReplayResult:
    geometry = manifest.request.geometry
    if geometry is None:
        raise ValueError("manifest request has no geometry")

    warnings: list[str] = list(manifest.migration_warnings)
    effective_limit = max_items if max_items is not None else manifest.query.max_items
    if effective_limit is None:
        effective_limit = 100
        warnings.append(
            "manifest did not record an Item Search limit; replay used a conservative "
            "default of 100"
        )
    if effective_limit < 1:
        raise ValueError("max_items must be at least 1")
    if manifest.query.max_items is not None and effective_limit != manifest.query.max_items:
        warnings.append(
            f"replay search limit changed from {manifest.query.max_items} to {effective_limit}"
        )

    # Late import avoids a module cycle: ScoutEngine builds manifests through this package.
    from stac_scout.scout import ScoutEngine

    _, probe = ScoutEngine(adapter).verify(
        manifest.request,
        manifest.collection_id,
        max_items=effective_limit,
    )

    previous = set(manifest.item_ids)
    current = {item.item_id for item in probe.items}
    retained = tuple(sorted(previous & current))
    raw_missing = tuple(sorted(previous - current))
    raw_new = tuple(sorted(current - previous))

    previous_complete = (
        manifest.observation.completeness is SearchCompleteness.COMPLETE
    )
    current_complete = probe.search.completeness is SearchCompleteness.COMPLETE

    confirmed_missing = raw_missing if current_complete else ()
    unresolved_missing = () if current_complete else raw_missing
    confirmed_new = raw_new if previous_complete else ()
    unresolved_new = () if previous_complete else raw_new

    if not previous_complete:
        warnings.append(
            "original manifest did not prove a complete Item result set; "
            "unseen replay Items cannot be confirmed as new"
        )
    if not current_complete:
        warnings.append(
            "replay did not prove a complete Item result set; "
            "unobserved original Items cannot be confirmed as missing"
        )

    return ReplayResult(
        probe=probe,
        previous_observation=manifest.observation,
        current_observation=probe.search,
        retained_item_ids=retained,
        confirmed_missing_item_ids=confirmed_missing,
        confirmed_new_item_ids=confirmed_new,
        unresolved_missing_item_ids=unresolved_missing,
        unresolved_new_item_ids=unresolved_new,
        comparison_complete=previous_complete and current_complete,
        warnings=tuple(dict.fromkeys(warnings)),
    )
