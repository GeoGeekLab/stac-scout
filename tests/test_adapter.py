from __future__ import annotations

from typing import Any

import pytest

from stac_scout.catalogs import GenericStacAdapter, LocationResolutionRequired
from stac_scout.models import ScoutRequest


class Record:
    def __init__(self, value: dict[str, Any]) -> None:
        self.value = value

    def to_dict(self) -> dict[str, Any]:
        return self.value


class Search:
    def items(self) -> list[Record]:
        return [Record({"id": "item-1"})]


class Client:
    def __init__(self) -> None:
        self.search_kwargs: dict[str, Any] | None = None

    def get_collections(self) -> list[Record]:
        return [Record({"id": "collection-1"})]

    def get_collection(self, collection_id: str) -> Record:
        return Record({"id": collection_id})

    def search(self, **kwargs: Any) -> Search:
        self.search_kwargs = kwargs
        return Search()


def test_generic_adapter_uses_structured_request(scout_request: ScoutRequest) -> None:
    client = Client()
    adapter = GenericStacAdapter("https://example.test/stac", client_factory=lambda _: client)

    items = adapter.search_items(scout_request, "collection-1", max_items=7)

    assert items == [{"id": "item-1"}]
    assert client.search_kwargs is not None
    assert client.search_kwargs["collections"] == ["collection-1"]
    assert client.search_kwargs["max_items"] == 7


def test_generic_adapter_requires_geometry(scout_request: ScoutRequest) -> None:
    adapter = GenericStacAdapter("https://example.test/stac", client_factory=lambda _: Client())
    without_geometry = scout_request.model_copy(update={"geometry": None, "place": "Singapore"})

    with pytest.raises(LocationResolutionRequired):
        adapter.search_items(without_geometry, "collection-1")


def test_generic_adapter_collection_methods() -> None:
    client = Client()
    adapter = GenericStacAdapter("https://example.test/stac", client_factory=lambda _: client)

    assert list(adapter.list_collections()) == [{"id": "collection-1"}]
    assert adapter.get_collection("collection-2") == {"id": "collection-2"}
