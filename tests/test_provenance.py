from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from stac_scout.models import (
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
from stac_scout.normalize import normalize_collection
from stac_scout.planning import odc_stac_recipe
from stac_scout.provenance import (
    MANIFEST_SCHEMA_VERSION,
    ReplayComparisonStatus,
    build_manifest,
    read_manifest,
    replay_manifest,
    write_manifest,
)


def _collection(*, title: str = "Collection One") -> dict[str, Any]:
    return {
        "id": "collection-1",
        "title": title,
        "description": "optical red nir",
        "license": "proprietary",
        "extent": {
            "spatial": {"bbox": [[-180, -90, 180, 90]]},
            "temporal": {"interval": [["2020-01-01T00:00:00Z", None]]},
        },
        "summaries": {
            "gsd": [10],
            "eo:bands": [
                {"common_name": "red"},
                {"common_name": "nir"},
            ],
        },
        "item_assets": {
            "B04": {
                "type": "image/tiff",
                "roles": ["data"],
                "gsd": 10,
                "eo:bands": [{"common_name": "red"}],
            },
            "B08": {
                "type": "image/tiff",
                "roles": ["data"],
                "gsd": 10,
                "eo:bands": [{"common_name": "nir"}],
            },
        },
    }


def _item(scout_request: ScoutRequest, item_id: str) -> dict[str, Any]:
    return {
        "id": item_id,
        "geometry": scout_request.geometry,
        "properties": {},
        "assets": {
            "B04": {
                "href": f"https://example.test/{item_id}/B04.tif?signature=ephemeral",
                "type": "image/tiff",
                "roles": ["data"],
                "gsd": 10,
                "file:size": 100,
                "eo:bands": [{"common_name": "red"}],
            },
            "B08": {
                "href": f"https://example.test/{item_id}/B08.tif?signature=ephemeral",
                "type": "image/tiff",
                "roles": ["data"],
                "gsd": 10,
                "file:size": 200,
                "eo:bands": [{"common_name": "nir"}],
            },
        },
    }


class Adapter:
    catalog_url = "https://example.test/stac"

    def __init__(
        self,
        item_ids: list[str],
        *,
        collection_title: str = "Collection One",
    ) -> None:
        self.item_ids = item_ids
        self.collection_title = collection_title
        self.last_max_items: int | None = None

    def inspect(self) -> CatalogCapabilities:
        return CatalogCapabilities(
            url=self.catalog_url,
            stac_version="1.0.0",
            item_search=True,
        )

    def list_collections(self) -> list[dict[str, Any]]:
        return [_collection(title=self.collection_title)]

    def get_collection(self, collection_id: str) -> dict[str, Any]:
        assert collection_id == "collection-1"
        return _collection(title=self.collection_title)

    def search_items(
        self,
        scout_request: ScoutRequest,
        collection_id: str,
        *,
        max_items: int = 100,
    ) -> list[dict[str, Any]]:
        assert collection_id == "collection-1"
        self.last_max_items = max_items
        return [_item(scout_request, item_id) for item_id in self.item_ids[:max_items]]


def _manifest(
    scout_request: ScoutRequest,
    *,
    item_ids: tuple[str, ...] = ("scene-1",),
    max_items: int = 100,
    completeness: SearchCompleteness = SearchCompleteness.COMPLETE,
):
    probe = AvailabilityProbe(
        status=VerificationStatus.VERIFIED_AVAILABLE,
        items_checked=len(item_ids),
        items=tuple(ItemEvidence(item_id=item_id) for item_id in item_ids),
    )
    historical_items = [_item(scout_request, item_id) for item_id in item_ids]
    collection = normalize_collection(_collection(), "https://example.test/stac")
    return build_manifest(
        scout_request,
        catalog_url="https://example.test/stac",
        collection_id="collection-1",
        provider_key="example",
        probe=probe,
        access_plan=AccessPlan(
            strategy="windowed-assets",
            assets=("B04", "B08"),
            estimated_bytes=300 * len(item_ids),
            output_crs=scout_request.target_crs,
            output_resolution=scout_request.target_resolution_m,
            resampling={"red": "bilinear", "nir": "bilinear"},
        ),
        search=SearchObservation(
            max_items=max_items,
            returned_items=len(item_ids),
            accepted_items=len(item_ids),
            completeness=completeness,
        ),
        collection=collection,
        catalog_capabilities=CatalogCapabilities(
            url="https://example.test/stac",
            stac_version="1.0.0",
            item_search=True,
        ),
        items=historical_items,
    )


def test_manifest_round_trip_and_provenance_snapshot(
    tmp_path: Path,
    scout_request: ScoutRequest,
) -> None:
    manifest = _manifest(scout_request)
    path = tmp_path / "scout.manifest.json"

    write_manifest(manifest, path)
    restored = read_manifest(path)

    assert restored == manifest
    assert restored.schema_version == MANIFEST_SCHEMA_VERSION == 1
    assert restored.search.completeness is SearchCompleteness.COMPLETE
    assert restored.search.max_items == 100
    assert restored.catalog_capabilities is not None
    assert restored.catalog_capabilities.item_search is True
    assert restored.collection_snapshot is not None
    assert restored.collection_snapshot.collection_id == "collection-1"
    assert restored.collection_fingerprint_sha256 is not None
    assert len(restored.collection_fingerprint_sha256) == 64
    assert restored.access_plan is not None
    assert restored.access_plan.assets == ("B04", "B08")
    assert len(restored.asset_metadata) == 2

    asset_payload = restored.asset_metadata[0].model_dump(mode="json")
    assert "href" not in asset_payload
    assert asset_payload["gsd_m"] == 10.0


def test_manifest_serialization_is_deterministic(
    tmp_path: Path,
    scout_request: ScoutRequest,
) -> None:
    manifest = _manifest(scout_request)
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    write_manifest(manifest, first)
    write_manifest(manifest, second)

    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")


def test_legacy_manifest_migrates_with_unknown_completeness(
    tmp_path: Path,
    scout_request: ScoutRequest,
) -> None:
    manifest = _manifest(scout_request)
    payload = manifest.model_dump(mode="json")
    for key in (
        "schema_version",
        "catalog_capabilities",
        "collection_snapshot",
        "collection_fingerprint_sha256",
        "search",
        "access_plan",
        "asset_metadata",
    ):
        payload.pop(key, None)

    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    restored = read_manifest(path)

    assert restored.schema_version == 1
    assert restored.search.completeness is SearchCompleteness.UNKNOWN
    assert restored.search.max_items is None
    assert restored.access_plan is None
    assert any("legacy unversioned manifest" in warning for warning in restored.warnings)


def test_future_manifest_schema_is_rejected(
    tmp_path: Path,
    scout_request: ScoutRequest,
) -> None:
    payload = _manifest(scout_request).model_dump(mode="json")
    payload["schema_version"] = 2
    path = tmp_path / "future.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported manifest schema version"):
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


def test_replay_reports_confirmed_drift_when_both_searches_complete(
    scout_request: ScoutRequest,
) -> None:
    adapter = Adapter(["scene-2"])
    result = replay_manifest(_manifest(scout_request), adapter)

    assert adapter.last_max_items == 100
    assert result.comparison_status is ReplayComparisonStatus.COMPLETE
    assert result.missing_item_ids == ("scene-1",)
    assert result.new_item_ids == ("scene-2",)
    assert result.unresolved_missing_item_ids == ()
    assert result.unresolved_new_item_ids == ()
    assert result.collection_changed is False


def test_replay_current_limit_makes_missing_direction_unresolved(
    scout_request: ScoutRequest,
) -> None:
    manifest = _manifest(
        scout_request,
        item_ids=("scene-1",),
        max_items=2,
        completeness=SearchCompleteness.COMPLETE,
    )
    result = replay_manifest(manifest, Adapter(["scene-2", "scene-3", "scene-4"]))

    assert result.comparison_status is ReplayComparisonStatus.PARTIAL
    assert result.missing_item_ids == ()
    assert result.unresolved_missing_item_ids == ("scene-1",)
    assert result.new_item_ids == ("scene-2", "scene-3")
    assert result.unresolved_new_item_ids == ()


def test_replay_historical_limit_makes_new_direction_unresolved(
    scout_request: ScoutRequest,
) -> None:
    manifest = _manifest(
        scout_request,
        item_ids=("scene-1",),
        max_items=1,
        completeness=SearchCompleteness.LIMIT_REACHED,
    )
    result = replay_manifest(
        manifest,
        Adapter(["scene-2"]),
        max_items=3,
    )

    assert result.comparison_status is ReplayComparisonStatus.PARTIAL
    assert result.missing_item_ids == ("scene-1",)
    assert result.unresolved_missing_item_ids == ()
    assert result.new_item_ids == ()
    assert result.unresolved_new_item_ids == ("scene-2",)
    assert any("differs from the manifest search limit" in warning for warning in result.warnings)


def test_replay_two_limit_reached_searches_do_not_confirm_drift(
    scout_request: ScoutRequest,
) -> None:
    manifest = _manifest(
        scout_request,
        item_ids=("scene-1", "scene-2"),
        max_items=2,
        completeness=SearchCompleteness.LIMIT_REACHED,
    )
    result = replay_manifest(manifest, Adapter(["scene-3", "scene-4", "scene-1"]))

    assert result.comparison_status is ReplayComparisonStatus.INCONCLUSIVE
    assert result.missing_item_ids == ()
    assert result.new_item_ids == ()
    assert result.unresolved_missing_item_ids == ("scene-1", "scene-2")
    assert result.unresolved_new_item_ids == ("scene-3", "scene-4")


def test_replay_over_100_items_and_changed_ordering_is_not_false_drift(
    scout_request: ScoutRequest,
) -> None:
    historical_ids = tuple(f"scene-{index:03d}" for index in range(100))
    manifest = _manifest(
        scout_request,
        item_ids=historical_ids,
        max_items=100,
        completeness=SearchCompleteness.LIMIT_REACHED,
    )
    current_ids = ["scene-100", *[f"scene-{index:03d}" for index in range(99)]]

    result = replay_manifest(manifest, Adapter(current_ids))

    assert result.search.completeness is SearchCompleteness.LIMIT_REACHED
    assert result.comparison_status is ReplayComparisonStatus.INCONCLUSIVE
    assert result.missing_item_ids == ()
    assert result.new_item_ids == ()
    assert result.unresolved_missing_item_ids == ("scene-099",)
    assert result.unresolved_new_item_ids == ("scene-100",)


def test_replay_detects_collection_snapshot_drift(scout_request: ScoutRequest) -> None:
    result = replay_manifest(
        _manifest(scout_request),
        Adapter(["scene-1"], collection_title="Renamed Collection"),
    )

    assert result.collection_changed is True


def test_search_observation_rejects_inconsistent_counts() -> None:
    with pytest.raises(ValueError, match="accepted_items"):
        SearchObservation(
            max_items=100,
            returned_items=1,
            accepted_items=2,
            completeness=SearchCompleteness.COMPLETE,
        )

    with pytest.raises(ValueError, match="complete search"):
        SearchObservation(
            max_items=1,
            returned_items=1,
            accepted_items=1,
            completeness=SearchCompleteness.COMPLETE,
        )
