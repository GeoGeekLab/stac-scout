from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, cast

from stac_scout.models import CatalogCapabilities, ScoutRequest

from .capabilities import inspect_catalog


class LocationResolutionRequired(ValueError):
    pass


class GenericStacAdapter:
    def __init__(
        self,
        catalog_url: str,
        *,
        client_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self.catalog_url = catalog_url
        self._client_factory = client_factory

    def _client(self) -> Any:
        if self._client_factory is not None:
            return self._client_factory(self.catalog_url)

        from pystac_client import Client

        return Client.open(self.catalog_url)

    def inspect(self) -> CatalogCapabilities:
        return inspect_catalog(self.catalog_url)

    def list_collections(self) -> Iterable[dict[str, Any]]:
        client = self._client()
        for collection in client.get_collections():
            yield cast(dict[str, Any], collection.to_dict())

    def get_collection(self, collection_id: str) -> dict[str, Any]:
        collection = self._client().get_collection(collection_id)
        return cast(dict[str, Any], collection.to_dict())

    def search_items(
        self,
        request: ScoutRequest,
        collection_id: str,
        *,
        max_items: int = 100,
    ) -> list[dict[str, Any]]:
        if request.geometry is None:
            raise LocationResolutionRequired(
                "a geometry is required for live item verification; resolve place names first"
            )

        interval = f"{request.datetime.start.isoformat()}/{request.datetime.end.isoformat()}"
        search = self._client().search(
            collections=[collection_id],
            intersects=request.geometry,
            datetime=interval,
            max_items=max_items,
        )
        return [cast(dict[str, Any], item.to_dict()) for item in search.items()]
