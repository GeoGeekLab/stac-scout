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
                "stac_extensions": [
                    "https://stac-extensions.github.io/sar/v1.0.0/schema.json"
                ],
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
                "stac_extensions": [
                    "https://stac-extensions.github.io/eo/v1.1.0/schema.json"
                ],
                "extent": {
                    "spatial": {"bbox": [[-180, -90, 180, 90]]},
                    "temporal": {"interval": [[None, None]]},
                },
                "summaries": {"gsd": [10]},
                "item_assets": {"red": {}, "nir": {}},
            },
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


def test_engine_verify_applies_known_cloud_constraint(
    scout_request: ScoutRequest,
) -> None:
    request = scout_request.model_copy(update={"max_cloud_cover": 20})
    engine = ScoutEngine(CloudAdapter([80, 10]))

    items, probe = engine.verify(request, "optical")

    assert [item["id"] for item in items] == ["scene-1"]
    assert probe.constraints[0].status is ConstraintStatus.PASS
    assert any("excluded 1 Item" in warning for warning in probe.warnings)


def test_engine_verify_preserves_unknown_cloud_constraint(
    scout_request: ScoutRequest,
) -> None:
    request = scout_request.model_copy(update={"max_cloud_cover": 20})
    engine = ScoutEngine(CloudAdapter([None]))

    items, probe = engine.verify(request, "optical")

    assert len(items) == 1
    assert probe.constraints[0].status is ConstraintStatus.UNKNOWN
    assert any("unknown cloud cover" in warning for warning in probe.warnings)


def test_engine_capped_cloud_search_is_inconclusive(
    scout_request: ScoutRequest,
) -> None:
    request = scout_request.model_copy(update={"max_cloud_cover": 20})
    engine = ScoutEngine(CloudAdapter([80, 10]))

    items, probe = engine.verify(request, "optical", max_items=1)

    assert items == []
    assert probe.status is VerificationStatus.INCONCLUSIVE
    assert probe.constraints[0].status is ConstraintStatus.UNKNOWN
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


def test_engine_verify_requires_geometry(scout_request: ScoutRequest) -> None:
    engine = ScoutEngine(Adapter())
    without_geometry = scout_request.model_copy(update={"geometry": None, "place": "Singapore"})

    try:
        engine.verify(without_geometry, "optical")
    except ValueError as exc:
        assert "geometry" in str(exc)
    else:
        raise AssertionError("expected geometry validation error")
