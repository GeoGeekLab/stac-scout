from __future__ import annotations

from typing import Any

from stac_scout.federation import FederatedScout
from stac_scout.models import ScoutRequest


class Adapter:
    def __init__(self, catalog_url: str, collections: list[dict[str, Any]]) -> None:
        self.catalog_url = catalog_url
        self.collections = collections

    def inspect(self) -> Any:
        raise NotImplementedError

    def list_collections(self) -> list[dict[str, Any]]:
        return self.collections

    def get_collection(self, collection_id: str) -> dict[str, Any]:
        return next(
            collection for collection in self.collections if collection["id"] == collection_id
        )

    def search_items(
        self,
        request: ScoutRequest,
        collection_id: str,
        *,
        max_items: int = 100,
    ) -> list[dict[str, Any]]:
        return []


class BrokenAdapter(Adapter):
    def list_collections(self) -> list[dict[str, Any]]:
        raise RuntimeError("catalog unavailable")


def _collection(identifier: str, doi: str) -> dict[str, Any]:
    return {
        "id": identifier,
        "title": "Surface Reflectance",
        "description": "optical vegetation red nir",
        "sci:doi": doi,
        "extent": {
            "spatial": {"bbox": [[-180, -90, 180, 90]]},
            "temporal": {"interval": [[None, None]]},
        },
        "summaries": {
            "gsd": [10],
            "eo:bands": [{"common_name": "red"}, {"common_name": "nir"}],
        },
    }


def test_federation_groups_exact_duplicates_and_keeps_provider_failures(
    scout_request: ScoutRequest,
) -> None:
    scout = FederatedScout(
        {
            "alpha": Adapter("https://a.test/stac", [_collection("a", "10.1234/shared")]),
            "beta": Adapter("https://b.test/stac", [_collection("b", "10.1234/shared")]),
            "broken": BrokenAdapter("https://broken.test/stac", []),
        }
    )

    result = scout.discover(scout_request)

    assert len(result.candidates) == 2
    assert len(result.duplicate_groups) == 1
    assert result.duplicate_groups[0].safe_to_collapse is True
    assert {candidate.provider_key for candidate in result.duplicate_groups[0].candidates} == {
        "alpha",
        "beta",
    }
    assert result.failures[0].provider_key == "broken"
    assert result.failures[0].error_type == "RuntimeError"


def test_federation_respects_global_limit(scout_request: ScoutRequest) -> None:
    scout = FederatedScout(
        {
            "alpha": Adapter(
                "https://a.test/stac",
                [_collection("one", "10.1/one"), _collection("two", "10.1/two")],
            )
        }
    )

    result = scout.discover(scout_request, per_provider_limit=2, limit=1)

    assert len(result.candidates) == 1
