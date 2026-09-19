from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from stac_scout.catalogs import CatalogAdapter
from stac_scout.constraints import evaluate_constraints
from stac_scout.discovery import RankedDataset, rank_collections
from stac_scout.models import (
    AccessPlan,
    AssetSigning,
    AvailabilityProbe,
    ConstraintCheck,
    DatasetCard,
    Manifest,
    ScoutRequest,
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


class ScoutEngine:
    def __init__(self, adapter: CatalogAdapter) -> None:
        self.adapter = adapter

    def discover(self, request: ScoutRequest, *, limit: int = 10) -> list[DiscoveryResult]:
        cards = [
            normalize_collection(raw, self.adapter.catalog_url)
            for raw in self.adapter.list_collections()
        ]
        ranked: list[RankedDataset] = rank_collections(cards, request, limit=limit)
        return [
            DiscoveryResult(
                dataset=entry.card,
                score=entry.score,
                constraints=evaluate_constraints(entry.card, request),
            )
            for entry in ranked
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
        items = self.adapter.search_items(request, collection_id, max_items=max_items)
        probe = probe_items(items, request.geometry)
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
        access_plan, missing = build_access_plan(
            request,
            items,
            probe,
            output_crs=output_crs,
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
