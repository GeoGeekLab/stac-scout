from __future__ import annotations

from typing import Any

import pytest
from pystac_client.exceptions import APIError

from stac_scout.catalogs import (
    GenericStacAdapter,
    LocationResolutionRequired,
    ProviderCapabilityError,
    ProviderMetadataError,
    ProviderProtocolError,
    ProviderRateLimitError,
)
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

    def get_collection(self, collection_id: str) -> Record | None:
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


def test_generic_adapter_maps_malformed_record_to_metadata_error() -> None:
    class MalformedRecord:
        def to_dict(self) -> dict[str, Any]:
            raise ValueError("invalid collection metadata")

    class MalformedClient(Client):
        def get_collections(self) -> list[Any]:
            return [MalformedRecord()]

    adapter = GenericStacAdapter(
        "https://example.test/stac",
        client_factory=lambda _: MalformedClient(),
    )

    with pytest.raises(ProviderMetadataError, match="collection metadata"):
        list(adapter.list_collections())


def test_generic_adapter_rejects_non_record_collection_metadata() -> None:
    class NonRecordClient(Client):
        def get_collections(self) -> list[Any]:
            return [object()]

    adapter = GenericStacAdapter(
        "https://example.test/stac",
        client_factory=lambda _: NonRecordClient(),
    )

    with pytest.raises(ProviderMetadataError, match="to_dict"):
        list(adapter.list_collections())


def test_generic_adapter_does_not_mask_search_call_type_error(
    scout_request: ScoutRequest,
) -> None:
    class BuggySearchClient(Client):
        def search(self, **kwargs: Any) -> Search:
            raise TypeError("internal search call bug")

    adapter = GenericStacAdapter(
        "https://example.test/stac",
        client_factory=lambda _: BuggySearchClient(),
    )

    with pytest.raises(TypeError, match="internal search call bug"):
        adapter.search_items(scout_request, "collection-1")


def test_generic_adapter_maps_unsupported_search_to_capability_error(
    scout_request: ScoutRequest,
) -> None:
    class UnsupportedClient(Client):
        def search(self, **kwargs: Any) -> Search:
            raise NotImplementedError("search unsupported")

    adapter = GenericStacAdapter(
        "https://example.test/stac",
        client_factory=lambda _: UnsupportedClient(),
    )

    with pytest.raises(ProviderCapabilityError, match="Item Search"):
        adapter.search_items(scout_request, "collection-1")


def test_generic_adapter_maps_api_rate_limit_to_typed_error(
    scout_request: ScoutRequest,
) -> None:
    class RateLimitedClient(Client):
        def search(self, **kwargs: Any) -> Search:
            error = APIError("rate limited")
            error.status_code = 429
            raise error

    adapter = GenericStacAdapter(
        "https://example.test/stac",
        client_factory=lambda _: RateLimitedClient(),
    )

    with pytest.raises(ProviderRateLimitError) as exc_info:
        adapter.search_items(scout_request, "collection-1")

    assert exc_info.value.status_code == 429
    assert exc_info.value.retryable is True


def test_generic_adapter_reports_missing_collection_as_protocol_error() -> None:
    class MissingClient(Client):
        def get_collection(self, collection_id: str) -> Record | None:
            return None

    adapter = GenericStacAdapter(
        "https://example.test/stac",
        client_factory=lambda _: MissingClient(),
    )

    with pytest.raises(ProviderProtocolError) as exc_info:
        adapter.get_collection("missing")

    assert exc_info.value.status_code == 404


def test_generic_adapter_does_not_mask_client_factory_programming_error() -> None:
    def broken_factory(url: str) -> Any:
        raise RuntimeError("internal factory bug")

    adapter = GenericStacAdapter(
        "https://example.test/stac",
        client_factory=broken_factory,
    )

    with pytest.raises(RuntimeError, match="internal factory bug"):
        list(adapter.list_collections())
