from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from stac_scout.catalogs import CatalogAdapter, ProviderMetadataError
from stac_scout.constraints import (
    ConstraintViolationError,
    evaluate_constraints,
    evaluate_item_constraints,
    has_failed_constraint,
    summarize_item_constraints,
)
from stac_scout.discovery import RankedDataset, rank_collections
from stac_scout.models import (
    AccessPlan,
    AssetSigning,
    AvailabilityProbe,
    ConstraintCheck,
    ConstraintStatus,
    DatasetCard,
    Manifest,
    ScoutRequest,
    VerificationStatus,
)
from stac_scout.normalize import normalize_collection
from stac_scout.planning import build_access_plan
from stac_scout.provenance import build_manifest
from stac_scout.verify import probe_items


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    dataset: DatasetCard
    score: float
    constraints: tuple[ConstraintCheck, ...]


@dataclass(frozen=True, slots=True)
class PlannedDataset:
    probe: AvailabilityProbe
    access_plan: AccessPlan
    manifest: Manifest
    missing_measurements: tuple[str, ...]


def _normalize_provider_collection(raw: dict[str, Any], catalog_url: str) -> DatasetCard:
    try:
        return normalize_collection(raw, catalog_url)
    except (KeyError, TypeError, ValueError) as exc:
        raise ProviderMetadataError(
            f"provider Collection metadata could not be normalized: {exc}"
        ) from exc


def _validate_provider_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            message = f"provider Item metadata at index {index} is not an object"
            raise ProviderMetadataError(message)
    return items


def _merge_constraint_checks(
    base: tuple[ConstraintCheck, ...],
    refinements: tuple[ConstraintCheck, ...],
) -> tuple[ConstraintCheck, ...]:
    refined = {check.name: check for check in refinements}
    merged = [refined.pop(check.name, check) for check in base]
    merged.extend(refined.values())
    return tuple(merged)


class ScoutEngine:
    def __init__(self, adapter: CatalogAdapter) -> None:
        self.adapter = adapter

    def discover(self, request: ScoutRequest, *, limit: int = 10) -> list[DiscoveryResult]:
        cards = [
            _normalize_provider_collection(raw, self.adapter.catalog_url)
            for raw in self.adapter.list_collections()
        ]

        constraints_by_collection: dict[tuple[str, str], tuple[ConstraintCheck, ...]] = {}
        eligible: list[DatasetCard] = []
        for card in cards:
            checks = evaluate_constraints(card, request)
            constraints_by_collection[(card.catalog_url, card.collection_id)] = checks
            if not has_failed_constraint(checks):
                eligible.append(card)

        ranked: list[RankedDataset] = rank_collections(
            eligible,
            request,
            limit=len(eligible),
        )
        ranked.sort(
            key=lambda entry: (
                sum(
                    check.status is ConstraintStatus.UNKNOWN
                    for check in constraints_by_collection[
                        (entry.card.catalog_url, entry.card.collection_id)
                    ]
                ),
                -entry.score,
                entry.card.collection_id,
            )
        )

        return [
            DiscoveryResult(
                dataset=entry.card,
                score=entry.score,
                constraints=constraints_by_collection[
                    (entry.card.catalog_url, entry.card.collection_id)
                ],
            )
            for entry in ranked[:limit]
        ]

    def verify(
        self,
        request: ScoutRequest,
        collection_id: str,
        *,
        max_items: int = 100,
    ) -> tuple[list[dict[str, Any]], AvailabilityProbe]:
        if request.geometry is None:
            raise ValueError("request geometry is required for live verification")

        collection = _normalize_provider_collection(
            self.adapter.get_collection(collection_id),
            self.adapter.catalog_url,
        )
        collection_checks = evaluate_constraints(collection, request)
        collection_failures = tuple(
            check for check in collection_checks if check.status is ConstraintStatus.FAIL
        )
        if collection_failures:
            raise ConstraintViolationError(
                "Collection-level hard constraints failed; refusing Item verification",
                collection_failures,
            )

        raw_items = _validate_provider_items(
            self.adapter.search_items(request, collection_id, max_items=max_items)
        )
        checks_by_item = [evaluate_item_constraints(item, request) for item in raw_items]
        items = [
            item
            for item, checks in zip(raw_items, checks_by_item, strict=True)
            if not has_failed_constraint(checks)
        ]

        item_summary = summarize_item_constraints(checks_by_item, request)
        warnings: list[str] = []
        failed_items = sum(has_failed_constraint(checks) for checks in checks_by_item)
        unknown_cloud_items = sum(
            any(
                check.name == "cloud_cover" and check.status is ConstraintStatus.UNKNOWN
                for check in checks
            )
            for checks in checks_by_item
        )

        if failed_items:
            warnings.append(
                f"excluded {failed_items} Item(s) that fail known Item-level hard constraints"
            )
        if unknown_cloud_items:
            warnings.append(
                f"{unknown_cloud_items} Item(s) have unknown cloud cover and remain unresolved"
            )

        capped = bool(raw_items) and len(raw_items) >= max_items
        if request.max_cloud_cover is not None and capped:
            warnings.append(
                "cloud-cover filtering was evaluated after the Item search reached its cap; "
                "additional matching Items may exist"
            )
            item_summary = tuple(
                check.model_copy(
                    update={
                        "status": ConstraintStatus.UNKNOWN,
                        "reason": (
                            "all inspected Items with known cloud cover failed, but the Item "
                            "search reached its cap so additional qualifying Items may exist"
                        ),
                    }
                )
                if check.name == "cloud_cover" and check.status is ConstraintStatus.FAIL
                else check
                for check in item_summary
            )

        constraints = _merge_constraint_checks(collection_checks, item_summary)
        probe = probe_items(items, request.geometry)
        status = probe.status
        if (
            not items
            and raw_items
            and capped
            and any(check.status is ConstraintStatus.UNKNOWN for check in constraints)
        ):
            status = VerificationStatus.INCONCLUSIVE

        probe = probe.model_copy(
            update={
                "status": status,
                "constraints": constraints,
                "warnings": tuple(dict.fromkeys((*probe.warnings, *warnings))),
            }
        )
        return items, probe

    def plan(
        self,
        request: ScoutRequest,
        collection_id: str,
        *,
        max_items: int = 100,
        output_crs: str | None = None,
    ) -> PlannedDataset:
        items, probe = self.verify(request, collection_id, max_items=max_items)

        verification_failures = tuple(
            check for check in probe.constraints if check.status is ConstraintStatus.FAIL
        )
        if verification_failures:
            raise ConstraintViolationError(
                "Item-level hard constraints failed; refusing to build an access plan",
                verification_failures,
            )

        access_plan, missing = build_access_plan(
            request,
            items,
            probe,
            output_crs=output_crs,
        )
        constraints = _merge_constraint_checks(probe.constraints, access_plan.constraints)
        planning_failures = tuple(
            check for check in constraints if check.status is ConstraintStatus.FAIL
        )
        if planning_failures:
            raise ConstraintViolationError(
                "planning-level hard constraints failed; refusing to build a manifest",
                planning_failures,
            )

        unresolved = tuple(
            check.name for check in constraints if check.status is ConstraintStatus.UNKNOWN
        )
        notes = list(access_plan.notes)
        if unresolved:
            notes.append(f"unresolved hard constraints: {', '.join(unresolved)}")
        access_plan = access_plan.model_copy(
            update={
                "constraints": constraints,
                "notes": tuple(dict.fromkeys(notes)),
            }
        )

        provider_key = getattr(self.adapter, "provider_key", None)
        if not isinstance(provider_key, str):
            provider_key = None
        asset_signing = getattr(self.adapter, "asset_signing", AssetSigning.NONE)
        if not isinstance(asset_signing, AssetSigning):
            asset_signing = AssetSigning.NONE

        manifest = build_manifest(
            request,
            catalog_url=self.adapter.catalog_url,
            collection_id=collection_id,
            provider_key=provider_key,
            asset_signing=asset_signing,
            probe=probe,
            access_plan=access_plan,
        )
        return PlannedDataset(
            probe=probe,
            access_plan=access_plan,
            manifest=manifest,
            missing_measurements=missing,
        )
