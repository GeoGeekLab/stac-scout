from __future__ import annotations

from typing import Any

import pytest

from stac_scout.constraints import ConstraintViolationError
from stac_scout.models import ConstraintStatus, DataType, ScoutRequest, VerificationStatus
from stac_scout.scout import ScoutEngine


class Adapter:
    catalog_url = "https://example.test/stac"

    def inspect(self) -> Any:
        raise NotImplementedError

    def list_collections(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "optical",
                "description": "vegetation red nir",
                "extent": {
                    "spatial": {"bbox": [[-180, -90, 180, 90]]},
                    "temporal": {"interval": [[None, None]]},
                },
                "summaries": {
                    "gsd": [10],
                    "eo:bands": [{"common_name": "red"}, {"common_name": "nir"}],
                },
            }
        ]

    def get_collection(self, collection_id: str) -> dict[str, Any]:
        return {"id": collection_id}

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
                    "red": {"file:size": 100},
                    "nir": {"file:size": 100},
                },
            }
        ]


class ModalityAdapter(Adapter):
    def list_collections(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "sar-high-text-score",
                "description": "optical vegetation red nir analysis",
                "stac_extensions": ["https://stac-extensions.github.io/sar/v1.0.0/schema.json"],
                "extent": {
                    "spatial": {"bbox": [[-180, -90, 180, 90]]},
                    "temporal": {"interval": [[None, None]]},
                },
                "summaries": {"gsd": [10]},
                "item_assets": {"red": {}, "nir": {}},
            },
            {
                "id": "optical",
                "description": "surface reflectance",
                "stac_extensions": ["https://stac-extensions.github.io/eo/v1.1.0/schema.json"],
                "extent": {
                    "spatial": {"bbox": [[-180, -90, 180, 90]]},
                    "temporal": {"interval": [[None, None]]},
                },
                "summaries": {"gsd": [10]},
                "item_assets": {"red": {}, "nir": {}},
            },
        ]

    def get_collection(self, collection_id: str) -> dict[str, Any]:
        return next(
            collection
            for collection in self.list_collections()
            if collection["id"] == collection_id
        )


class AmbiguousAssetAdapter(Adapter):
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
                    "A": {
                        "type": "image/tiff",
                        "roles": ["data"],
                        "eo:bands": [{"common_name": "red"}],
                    },
                    "B": {
                        "type": "image/tiff",
                        "roles": ["data"],
                        "eo:bands": [{"common_name": "red"}],
                    },
                },
            }
        ]


class CoarseAssetAdapter(Adapter):
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
                    "red": {
                        "type": "image/tiff",
                        "roles": ["data"],
                        "gsd": 30,
                    }
                },
            }
        ]


class CloudAdapter(Adapter):
    def __init__(self, cloud_values: list[float | None]) -> None:
        self.cloud_values = cloud_values

    def search_items(
        self,
        scout_request: ScoutRequest,
        collection_id: str,
        *,
        max_items: int = 100,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for index, cloud_cover in enumerate(self.cloud_values[:max_items]):
            properties: dict[str, Any] = {}
            if cloud_cover is not None:
                properties["eo:cloud_cover"] = cloud_cover
            items.append(
                {
                    "id": f"scene-{index}",
                    "geometry": scout_request.geometry,
                    "properties": properties,
                    "assets": {
                        "red": {"file:size": 100},
                        "nir": {"file:size": 100},
                    },
                }
            )
        return items


def _constraint_status(probe: Any, name: str) -> ConstraintStatus:
    return next(check.status for check in probe.constraints if check.name == name)


def test_engine_discovers_and_plans(scout_request: ScoutRequest) -> None:
    engine = ScoutEngine(Adapter())

    discovery = engine.discover(scout_request)
    planned = engine.plan(scout_request, "optical")

    assert discovery[0].dataset.collection_id == "optical"
    assert planned.probe.items_checked == 1
    assert planned.access_plan.assets == ("red", "nir")
    assert planned.manifest.collection_id == "optical"


def test_engine_filters_hard_constraint_failures_before_ranking(
    scout_request: ScoutRequest,
) -> None:
    request = scout_request.model_copy(update={"data_type": DataType.OPTICAL})
    engine = ScoutEngine(ModalityAdapter())

    discovery = engine.discover(request)

    assert [result.dataset.collection_id for result in discovery] == ["optical"]
    assert discovery[0].constraints[0].name == "data_type"
    assert discovery[0].constraints[0].status is ConstraintStatus.PASS


def test_engine_direct_verify_rejects_collection_constraint_failure(
    scout_request: ScoutRequest,
) -> None:
    request = scout_request.model_copy(update={"data_type": DataType.OPTICAL})
    engine = ScoutEngine(ModalityAdapter())

    with pytest.raises(ConstraintViolationError, match="Collection-level hard constraints failed"):
        engine.verify(request, "sar-high-text-score")


def test_engine_verify_applies_known_cloud_constraint(
    scout_request: ScoutRequest,
) -> None:
    request = scout_request.model_copy(update={"max_cloud_cover": 20})
    engine = ScoutEngine(CloudAdapter([80, 10]))

    items, probe = engine.verify(request, "optical")

    assert [item["id"] for item in items] == ["scene-1"]
    assert _constraint_status(probe, "cloud_cover") is ConstraintStatus.PASS
    assert any("excluded 1 Item" in warning for warning in probe.warnings)


def test_engine_verify_preserves_unknown_cloud_constraint(
    scout_request: ScoutRequest,
) -> None:
    request = scout_request.model_copy(update={"max_cloud_cover": 20})
    engine = ScoutEngine(CloudAdapter([None]))

    items, probe = engine.verify(request, "optical")

    assert len(items) == 1
    assert _constraint_status(probe, "cloud_cover") is ConstraintStatus.UNKNOWN
    assert any("unknown cloud cover" in warning for warning in probe.warnings)


def test_engine_capped_cloud_search_is_inconclusive(
    scout_request: ScoutRequest,
) -> None:
    request = scout_request.model_copy(update={"max_cloud_cover": 20})
    engine = ScoutEngine(CloudAdapter([80, 10]))

    items, probe = engine.verify(request, "optical", max_items=1)

    assert items == []
    assert probe.status is VerificationStatus.INCONCLUSIVE
    assert _constraint_status(probe, "cloud_cover") is ConstraintStatus.UNKNOWN
    assert any("reached its cap" in warning for warning in probe.warnings)


def test_engine_plan_rejects_known_cloud_failure(
    scout_request: ScoutRequest,
) -> None:
    request = scout_request.model_copy(update={"max_cloud_cover": 20})
    engine = ScoutEngine(CloudAdapter([80]))

    with pytest.raises(ConstraintViolationError, match="Item-level hard constraints failed"):
        engine.plan(request, "optical")


def test_engine_plan_rejects_volume_budget_failure(
    scout_request: ScoutRequest,
) -> None:
    request = scout_request.model_copy(update={"max_data_volume_bytes": 100})
    engine = ScoutEngine(Adapter())

    with pytest.raises(ConstraintViolationError, match="planning-level hard constraints failed"):
        engine.plan(request, "optical")


def test_engine_plan_rejects_ambiguous_asset_selection(
    scout_request: ScoutRequest,
) -> None:
    request = scout_request.model_copy(
        update={
            "required_measurements": ("red",),
            "max_source_resolution_m": None,
        }
    )
    engine = ScoutEngine(AmbiguousAssetAdapter())

    with pytest.raises(ConstraintViolationError, match="planning-level hard constraints failed"):
        engine.plan(request, "optical")


def test_engine_plan_rejects_selected_asset_over_source_resolution(
    scout_request: ScoutRequest,
) -> None:
    request = scout_request.model_copy(
        update={
            "required_measurements": ("red",),
            "max_source_resolution_m": 10,
        }
    )
    engine = ScoutEngine(CoarseAssetAdapter())

    with pytest.raises(ConstraintViolationError, match="planning-level hard constraints failed"):
        engine.plan(request, "optical")


def test_engine_verify_requires_geometry(scout_request: ScoutRequest) -> None:
    engine = ScoutEngine(Adapter())
    without_geometry = scout_request.model_copy(update={"geometry": None, "place": "Singapore"})

    try:
        engine.verify(without_geometry, "optical")
    except ValueError as exc:
        assert "geometry" in str(exc)
    else:
        raise AssertionError("expected geometry validation error")
