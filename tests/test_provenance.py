from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from stac_scout.models import (
    CURRENT_MANIFEST_SCHEMA_VERSION,
    AccessPlan,
    AssetSigning,
    AvailabilityProbe,
    CatalogCapabilities,
    ItemEvidence,
    ScoutRequest,
    SearchCompleteness,
    SearchObservation,
    VerificationStatus,
)
from stac_scout.planning import odc_stac_recipe
from stac_scout.provenance import (
    ManifestIntegrityError,
    UnsupportedManifestVersionError,
    build_manifest,
    canonical_fingerprint,
    read_manifest,
    replay_manifest,
    write_manifest,
)
from stac_scout.scout import ScoutEngine


def _item(identifier: str, request: ScoutRequest) -> dict[str, Any]:
    return {
        "id": identifier,
        "geometry": request.geometry,
        "properties": {},
        "assets": {},
    }


class Adapter:
    catalog_url = "https://example.test/stac"

    def __init__(self, item_ids: tuple[str, ...] = ("scene-2",)) -> None:
        self.item_ids = item_ids

    def inspect(self) -> Any:
        raise NotImplementedError

    def list_collections(self) -> list[dict[str, Any]]:
        return []

    def get_collection(self, collection_id: str) -> dict[str, Any]:
        return {"id": collection_id}

    def search_items(
        self,
        scout_request: ScoutRequest,
        collection_id: str,
        *,
        max_items: int = 100,
    ) -> list[dict[str, Any]]:
        return [_item(identifier, scout_request) for identifier in self.item_ids[:max_items]]


class PlanningAdapter(Adapter):
    provider_key = "example-provider"
    asset_signing = AssetSigning.NONE

    def inspect(self) -> CatalogCapabilities:
        return CatalogCapabilities(
            url=self.catalog_url,
            stac_version="1.0.0",
            item_search=True,
        )

    def get_collection(self, collection_id: str) -> dict[str, Any]:
        return {
            "id": collection_id,
            "description": "surface reflectance",
            "extent": {
                "spatial": {"bbox": [[-180, -90, 180, 90]]},
                "temporal": {"interval": [[None, None]]},
            },
            "summaries": {"gsd": [10]},
            "item_assets": {
                "B04": {
                    "gsd": 10,
                    "roles": ["data"],
                    "eo:bands": [{"common_name": "red"}],
                },
                "B08": {
                    "gsd": 10,
                    "roles": ["data"],
                    "eo:bands": [{"common_name": "nir"}],
                },
            },
        }

    def search_items(
        self,
        scout_request: ScoutRequest,
        collection_id: str,
        *,
        max_items: int = 100,
    ) -> list[dict[str, Any]]:
        return [
            {
                "id": "scene-1",
                "geometry": scout_request.geometry,
                "properties": {},
                "assets": {
                    "B04": {
                        "gsd": 10,
                        "roles": ["data"],
                        "eo:bands": [{"common_name": "red"}],
                        "file:size": 100,
                    },
                    "B08": {
                        "gsd": 10,
                        "roles": ["data"],
                        "eo:bands": [{"common_name": "nir"}],
                        "file:size": 100,
                    },
                },
            }
        ][:max_items]


def _manifest(
    scout_request: ScoutRequest,
    *,
    item_ids: tuple[str, ...] = ("scene-1",),
    max_items: int = 100,
    completeness: SearchCompleteness = SearchCompleteness.COMPLETE,
):
    observation = SearchObservation(
        max_items=max_items,
        items_observed=(max_items if completeness is SearchCompleteness.CAPPED else len(item_ids)),
        items_retained=len(item_ids),
        completeness=completeness,
        pagination_exhausted=completeness is SearchCompleteness.COMPLETE,
    )
    probe = AvailabilityProbe(
        status=VerificationStatus.VERIFIED_AVAILABLE,
        items_checked=len(item_ids),
        items=tuple(ItemEvidence(item_id=item_id) for item_id in item_ids),
        search=observation,
    )
    return build_manifest(
        scout_request,
        catalog_url="https://example.test/stac",
        collection_id="collection-1",
        probe=probe,
        access_plan=AccessPlan(strategy="windowed-assets", assets=("B04", "B08")),
    )


def test_manifest_round_trip(tmp_path: Path, scout_request: ScoutRequest) -> None:
    manifest = _manifest(scout_request)
    path = tmp_path / "scout.manifest.json"

    write_manifest(manifest, path)

    restored = read_manifest(path)
    assert restored == manifest
    assert restored.schema_version == CURRENT_MANIFEST_SCHEMA_VERSION
    assert restored.query.max_items == 100
    assert restored.observation.completeness is SearchCompleteness.COMPLETE
    assert restored.access_plan is not None


def test_manifest_fingerprints_are_canonical() -> None:
    assert canonical_fingerprint({"b": 2, "a": 1}) == canonical_fingerprint(
        {"a": 1, "b": 2}
    )


def test_engine_manifest_records_decision_evidence(scout_request: ScoutRequest) -> None:
    planned = ScoutEngine(PlanningAdapter()).plan(
        scout_request,
        "collection-1",
        max_items=100,
    )

    manifest = planned.manifest

    assert manifest.provider_key == "example-provider"
    assert manifest.adapter_type == "PlanningAdapter"
    assert manifest.catalog_capabilities is not None
    assert manifest.catalog_capabilities.item_search is True
    assert manifest.collection_snapshot is not None
    assert manifest.collection_snapshot.collection_id == "collection-1"
    assert manifest.collection_fingerprint is not None
    assert len(manifest.request_fingerprint) == 64
    assert len(manifest.query_fingerprint) == 64
    assert manifest.observation.completeness is SearchCompleteness.COMPLETE
    assert manifest.observation.items_observed == 1
    assert manifest.access_plan == planned.access_plan
    assert manifest.item_evidence == planned.probe.items


def test_legacy_unversioned_manifest_migrates_conservatively(
    tmp_path: Path,
    scout_request: ScoutRequest,
) -> None:
    current = _manifest(scout_request)
    payload = current.model_dump(mode="json")

    for key in (
        "schema_version",
        "migrated_from_schema_version",
        "request_fingerprint",
        "adapter_type",
        "catalog_capabilities",
        "collection_snapshot",
        "collection_fingerprint",
        "query_fingerprint",
        "observation",
        "item_evidence",
        "access_plan",
        "migration_warnings",
    ):
        payload.pop(key, None)
    payload["query"].pop("max_items", None)

    path = tmp_path / "legacy.manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    migrated = read_manifest(path)

    assert migrated.schema_version == CURRENT_MANIFEST_SCHEMA_VERSION
    assert migrated.migrated_from_schema_version == "legacy-unversioned"
    assert migrated.observation.completeness is SearchCompleteness.UNKNOWN
    assert migrated.observation.max_items is None
    assert migrated.access_plan is None
    assert [item.item_id for item in migrated.item_evidence] == ["scene-1"]
    assert migrated.migration_warnings


def test_manifest_reader_detects_request_fingerprint_drift(
    tmp_path: Path,
    scout_request: ScoutRequest,
) -> None:
    payload = _manifest(scout_request).model_dump(mode="json")
    payload["request"]["task"] = "tampered task"
    path = tmp_path / "tampered.manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ManifestIntegrityError, match="request fingerprint"):
        read_manifest(path)


def test_unknown_future_manifest_version_is_rejected(
    tmp_path: Path,
    scout_request: ScoutRequest,
) -> None:
    payload = _manifest(scout_request).model_dump(mode="json")
    payload["schema_version"] = "2.0"
    path = tmp_path / "future.manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(UnsupportedManifestVersionError, match=r"2\.0"):
        read_manifest(path)


def test_recipe_contains_reproducible_query(scout_request: ScoutRequest) -> None:
    recipe = odc_stac_recipe(_manifest(scout_request))

    assert "Client.open('https://example.test/stac')" in recipe
    assert "'collection-1'" in recipe
    assert "'B04', 'B08'" in recipe
    assert "resolution=" not in recipe


def test_recipe_uses_explicit_target_resolution_only(scout_request: ScoutRequest) -> None:
    request = scout_request.model_copy(
        update={
            "max_source_resolution_m": 30,
            "target_crs": "EPSG:3857",
            "target_resolution_m": 20,
        }
    )

    recipe = odc_stac_recipe(_manifest(request))

    assert "crs='EPSG:3857'" in recipe
    assert "resolution=20" in recipe
    assert "resolution=30" not in recipe


def test_planetary_computer_recipe_uses_official_signer(scout_request: ScoutRequest) -> None:
    manifest = _manifest(scout_request).model_copy(
        update={
            "provider_key": "planetary-computer",
            "asset_signing": AssetSigning.PLANETARY_COMPUTER,
        }
    )

    recipe = odc_stac_recipe(manifest)

    assert "import planetary_computer" in recipe
    assert "modifier=planetary_computer.sign_inplace" in recipe


def test_provider_dependent_signing_refuses_generic_recipe(scout_request: ScoutRequest) -> None:
    manifest = _manifest(scout_request).model_copy(
        update={"asset_signing": AssetSigning.PROVIDER_DEPENDENT}
    )

    with pytest.raises(ValueError, match="provider-dependent"):
        odc_stac_recipe(manifest)


def test_replay_confirms_drift_when_both_searches_are_complete(
    scout_request: ScoutRequest,
) -> None:
    result = replay_manifest(_manifest(scout_request), Adapter(("scene-2",)))

    assert result.comparison_complete is True
    assert result.retained_item_ids == ()
    assert result.confirmed_missing_item_ids == ("scene-1",)
    assert result.confirmed_new_item_ids == ("scene-2",)
    assert result.unresolved_missing_item_ids == ()
    assert result.unresolved_new_item_ids == ()
    assert result.missing_item_ids == ("scene-1",)
    assert result.new_item_ids == ("scene-2",)


def test_replay_does_not_report_capped_reordering_as_confirmed_drift(
    scout_request: ScoutRequest,
) -> None:
    previous_ids = tuple(f"scene-{index:03d}" for index in range(100))
    current_ids = tuple(f"scene-{index:03d}" for index in range(50, 150))
    manifest = _manifest(
        scout_request,
        item_ids=previous_ids,
        max_items=100,
        completeness=SearchCompleteness.CAPPED,
    )

    result = replay_manifest(manifest, Adapter(current_ids))

    assert result.comparison_complete is False
    assert len(result.retained_item_ids) == 50
    assert result.confirmed_missing_item_ids == ()
    assert result.confirmed_new_item_ids == ()
    assert result.unresolved_missing_item_ids == tuple(
        f"scene-{index:03d}" for index in range(50)
    )
    assert result.unresolved_new_item_ids == tuple(
        f"scene-{index:03d}" for index in range(100, 150)
    )


def test_replay_with_larger_complete_search_only_confirms_missing_side(
    scout_request: ScoutRequest,
) -> None:
    previous_ids = tuple(f"scene-{index:03d}" for index in range(100))
    current_ids = tuple(f"scene-{index:03d}" for index in range(50, 150))
    manifest = _manifest(
        scout_request,
        item_ids=previous_ids,
        max_items=100,
        completeness=SearchCompleteness.CAPPED,
    )

    result = replay_manifest(
        manifest,
        Adapter(current_ids),
        max_items=200,
    )

    assert result.current_observation.completeness is SearchCompleteness.COMPLETE
    assert result.confirmed_missing_item_ids == tuple(
        f"scene-{index:03d}" for index in range(50)
    )
    assert result.confirmed_new_item_ids == ()
    assert result.unresolved_new_item_ids == tuple(
        f"scene-{index:03d}" for index in range(100, 150)
    )
    assert any("search limit changed" in warning for warning in result.warnings)
