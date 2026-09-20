from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from stac_scout.catalogs import CatalogAdapter, ProviderMetadataError
from stac_scout.constraints import (
    evaluate_item_constraints,
    has_failed_constraint,
    summarize_item_constraints,
)
from stac_scout.models import (
    AvailabilityProbe,
    ConstraintStatus,
    Manifest,
    SearchCompleteness,
    SearchObservation,
    VerificationStatus,
)
from stac_scout.normalize import normalize_collection
from stac_scout.verify import probe_items

from .manifest import _collection_snapshot, _fingerprint


class ReplayComparisonStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True, slots=True)
class ReplayResult:
    probe: AvailabilityProbe
    search: SearchObservation
    comparison_status: ReplayComparisonStatus
    retained_item_ids: tuple[str, ...]
    missing_item_ids: tuple[str, ...]
    new_item_ids: tuple[str, ...]
    unresolved_missing_item_ids: tuple[str, ...]
    unresolved_new_item_ids: tuple[str, ...]
    collection_changed: bool | None
    warnings: tuple[str, ...]


def _validated_items(items: Sequence[Any]) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            message = f"provider Item metadata at index {index} is not an object"
            raise ProviderMetadataError(message)
        validated.append(item)
    return validated


def _search_observation(
    *,
    max_items: int,
    returned_items: int,
    accepted_items: int,
) -> SearchObservation:
    if returned_items < max_items:
        completeness = SearchCompleteness.COMPLETE
    elif returned_items == max_items:
        completeness = SearchCompleteness.LIMIT_REACHED
    else:
        completeness = SearchCompleteness.UNKNOWN

    return SearchObservation(
        max_items=max_items,
        returned_items=returned_items,
        accepted_items=accepted_items,
        completeness=completeness,
    )


def _comparison_status(
    previous: SearchCompleteness,
    current: SearchCompleteness,
) -> ReplayComparisonStatus:
    previous_complete = previous is SearchCompleteness.COMPLETE
    current_complete = current is SearchCompleteness.COMPLETE
    if previous_complete and current_complete:
        return ReplayComparisonStatus.COMPLETE
    if previous_complete or current_complete:
        return ReplayComparisonStatus.PARTIAL
    return ReplayComparisonStatus.INCONCLUSIVE


def replay_manifest(
    manifest: Manifest,
    adapter: CatalogAdapter,
    *,
    max_items: int | None = None,
) -> ReplayResult:
    geometry = manifest.request.geometry
    if geometry is None:
        raise ValueError("manifest request has no geometry")

    warnings: list[str] = []
    effective_max_items = max_items
    if effective_max_items is None:
        effective_max_items = manifest.search.max_items
    if effective_max_items is None:
        effective_max_items = 100
        warnings.append(
            "historical manifest did not record max_items; replay used the legacy default of 100"
        )
    if effective_max_items < 1:
        raise ValueError("max_items must be at least 1")

    raw_items = _validated_items(
        adapter.search_items(
            manifest.request,
            manifest.collection_id,
            max_items=effective_max_items,
        )
    )
    checks_by_item = [evaluate_item_constraints(item, manifest.request) for item in raw_items]
    items = [
        item
        for item, checks in zip(raw_items, checks_by_item, strict=True)
        if not has_failed_constraint(checks)
    ]
    item_summary = summarize_item_constraints(checks_by_item, manifest.request)

    failed_items = sum(has_failed_constraint(checks) for checks in checks_by_item)
    if failed_items:
        warnings.append(
            f"excluded {failed_items} Item(s) that fail current Item-level hard constraints"
        )

    unknown_cloud_items = sum(
        any(
            check.name == "cloud_cover" and check.status is ConstraintStatus.UNKNOWN
            for check in checks
        )
        for checks in checks_by_item
    )
    if unknown_cloud_items:
        warnings.append(
            f"{unknown_cloud_items} Item(s) have unknown cloud cover in the replay"
        )

    current_search = _search_observation(
        max_items=effective_max_items,
        returned_items=len(raw_items),
        accepted_items=len(items),
    )
    if current_search.completeness is SearchCompleteness.LIMIT_REACHED:
        warnings.append(
            "current replay search reached max_items; some apparent differences may be ordering "
            "or truncation artifacts"
        )
        if manifest.request.max_cloud_cover is not None:
            item_summary = tuple(
                check.model_copy(
                    update={
                        "status": ConstraintStatus.UNKNOWN,
                        "reason": (
                            "all inspected Items with known cloud cover failed, but the replay "
                            "search reached its cap so additional qualifying Items may exist"
                        ),
                    }
                )
                if check.name == "cloud_cover" and check.status is ConstraintStatus.FAIL
                else check
                for check in item_summary
            )
    elif current_search.completeness is SearchCompleteness.UNKNOWN:
        warnings.append(
            "current provider returned more Items than max_items; search completeness is unknown"
        )

    if max_items is not None and max_items != manifest.search.max_items:
        warnings.append(
            "replay max_items differs from the manifest search limit; comparability depends on "
            "result-set completeness"
        )

    probe = probe_items(items, geometry)
    probe_status = probe.status
    if (
        not items
        and raw_items
        and current_search.completeness is SearchCompleteness.LIMIT_REACHED
        and any(check.status is ConstraintStatus.UNKNOWN for check in item_summary)
    ):
        probe_status = VerificationStatus.INCONCLUSIVE

    probe = probe.model_copy(
        update={
            "status": probe_status,
            "constraints": item_summary,
            "warnings": tuple(dict.fromkeys(warnings)),
        }
    )

    previous = set(manifest.item_ids)
    current = {item.item_id for item in probe.items}
    retained = tuple(sorted(previous & current))
    missing_candidates = tuple(sorted(previous - current))
    new_candidates = tuple(sorted(current - previous))

    previous_complete = manifest.search.completeness is SearchCompleteness.COMPLETE
    current_complete = current_search.completeness is SearchCompleteness.COMPLETE

    confirmed_missing = missing_candidates if current_complete else ()
    unresolved_missing = () if current_complete else missing_candidates
    confirmed_new = new_candidates if previous_complete else ()
    unresolved_new = () if previous_complete else new_candidates

    if unresolved_missing:
        warnings.append(
            "some previously observed Item IDs were not seen, but the current search is not "
            "proven complete"
        )
    if unresolved_new:
        warnings.append(
            "some currently observed Item IDs were absent from the manifest, but the historical "
            "search was not proven complete"
        )

    collection_changed: bool | None = None
    if manifest.collection_fingerprint_sha256 is not None:
        try:
            current_collection = normalize_collection(
                adapter.get_collection(manifest.collection_id),
                adapter.catalog_url,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderMetadataError(
                f"current Collection metadata could not be normalized: {exc}"
            ) from exc
        current_fingerprint = _fingerprint(_collection_snapshot(current_collection))
        collection_changed = current_fingerprint != manifest.collection_fingerprint_sha256
    else:
        warnings.append(
            "manifest has no Collection fingerprint; Collection metadata drift cannot be assessed"
        )

    return ReplayResult(
        probe=probe.model_copy(
            update={"warnings": tuple(dict.fromkeys((*probe.warnings, *warnings)))}
        ),
        search=current_search,
        comparison_status=_comparison_status(
            manifest.search.completeness,
            current_search.completeness,
        ),
        retained_item_ids=retained,
        missing_item_ids=confirmed_missing,
        new_item_ids=confirmed_new,
        unresolved_missing_item_ids=unresolved_missing,
        unresolved_new_item_ids=unresolved_new,
        collection_changed=collection_changed,
        warnings=tuple(dict.fromkeys(warnings)),
    )
