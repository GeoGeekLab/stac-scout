from __future__ import annotations

from typing import Any

from stac_scout.models import ScoutRequest
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


def test_engine_discovers_and_plans(scout_request: ScoutRequest) -> None:
    engine = ScoutEngine(Adapter())

    discovery = engine.discover(scout_request)
    planned = engine.plan(scout_request, "optical")

    assert discovery[0].dataset.collection_id == "optical"
    assert planned.probe.items_checked == 1
    assert planned.access_plan.assets == ("red", "nir")
    assert planned.manifest.collection_id == "optical"


def test_engine_verify_requires_geometry(scout_request: ScoutRequest) -> None:
    engine = ScoutEngine(Adapter())
    without_geometry = scout_request.model_copy(update={"geometry": None, "place": "Singapore"})

    try:
        engine.verify(without_geometry, "optical")
    except ValueError as exc:
        assert "geometry" in str(exc)
    else:
        raise AssertionError("expected geometry validation error")
