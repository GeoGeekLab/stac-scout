from __future__ import annotations

from pathlib import Path
from typing import Any

from stac_scout.models import (
    AccessPlan,
    AvailabilityProbe,
    ItemEvidence,
    ScoutRequest,
    VerificationStatus,
)
from stac_scout.planning import odc_stac_recipe
from stac_scout.provenance import build_manifest, read_manifest, replay_manifest, write_manifest


class Adapter:
    catalog_url = "https://example.test/stac"

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
        return [
            {
                "id": "scene-2",
                "geometry": scout_request.geometry,
                "properties": {},
                "assets": {},
            }
        ]


def _manifest(scout_request: ScoutRequest):
    probe = AvailabilityProbe(
        status=VerificationStatus.VERIFIED_AVAILABLE,
        items_checked=1,
        items=(ItemEvidence(item_id="scene-1"),),
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

    assert read_manifest(path) == manifest


def test_recipe_contains_reproducible_query(scout_request: ScoutRequest) -> None:
    recipe = odc_stac_recipe(_manifest(scout_request))

    assert "Client.open('https://example.test/stac')" in recipe
    assert "'collection-1'" in recipe
    assert "'B04', 'B08'" in recipe


def test_replay_reports_item_drift(scout_request: ScoutRequest) -> None:
    result = replay_manifest(_manifest(scout_request), Adapter())

    assert result.missing_item_ids == ("scene-1",)
    assert result.new_item_ids == ("scene-2",)
