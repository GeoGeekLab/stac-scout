from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, TypeVar, cast

import pystac
from pystac_client.exceptions import APIError
from pystac_client.stac_api_io import StacApiIO

from stac_scout.models import AssetSigning, CatalogCapabilities, ScoutRequest

from .capabilities import inspect_catalog
from .errors import (
    ProviderCapabilityError,
    ProviderMetadataError,
    ProviderProtocolError,
    provider_error_from_api_error,
)
from .network import ProviderNetworkPolicy

_T = TypeVar("_T")


class LocationResolutionRequired(ValueError):
    pass


def _record_dict(record: Any, *, context: str) -> dict[str, Any]:
    serializer = getattr(record, "to_dict", None)
    if not callable(serializer):
        raise ProviderMetadataError(f"{context}: record does not provide to_dict()")

    try:
        payload = serializer()
    except (pystac.STACError, KeyError, TypeError, ValueError) as exc:
        raise ProviderMetadataError(f"{context}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ProviderMetadataError(f"{context}: expected an object")
    return cast(dict[str, Any], payload)


class GenericStacAdapter:
    def __init__(
        self,
        catalog_url: str,
        *,
        provider_key: str | None = None,
        asset_signing: AssetSigning = AssetSigning.NONE,
        client_factory: Callable[[str], Any] | None = None,
        network_policy: ProviderNetworkPolicy | None = None,
    ) -> None:
        self.catalog_url = catalog_url
        self.provider_key = provider_key
        self.asset_signing = asset_signing
        self._client_factory = client_factory
        self.network_policy = network_policy or ProviderNetworkPolicy()

    def _provider_call(
        self,
        operation: Callable[[], _T],
        *,
        capability_context: str | None = None,
    ) -> _T:
        try:
            return operation()
        except APIError as exc:
            raise provider_error_from_api_error(exc) from exc
        except NotImplementedError as exc:
            if capability_context is None:
                raise
            raise ProviderCapabilityError(capability_context) from exc

    def _metadata_call(
        self,
        operation: Callable[[], _T],
        *,
        context: str,
        capability_context: str | None = None,
    ) -> _T:
        try:
            return self._provider_call(
                operation,
                capability_context=capability_context,
            )
        except (pystac.STACError, KeyError, TypeError, ValueError) as exc:
            raise ProviderMetadataError(f"{context}: {exc}") from exc

    def _client(self) -> Any:
        if self._client_factory is not None:
            return self._client_factory(self.catalog_url)

        from pystac_client import Client

        stac_io = StacApiIO(
            timeout=self.network_policy.timeout,
            max_retries=self.network_policy.retry(),
        )
        return self._metadata_call(
            lambda: Client.open(
                self.catalog_url,
                stac_io=stac_io,
                timeout=self.network_policy.timeout,
            ),
            context="provider root metadata is invalid",
        )

    def inspect(self) -> CatalogCapabilities:
        return inspect_catalog(
            self.catalog_url,
            network_policy=self.network_policy,
        )

    def list_collections(self) -> Iterable[dict[str, Any]]:
        client = self._client()

        def load() -> list[dict[str, Any]]:
            records = self._provider_call(client.get_collections)
            return [
                _record_dict(collection, context="collection metadata is invalid")
                for collection in records
            ]

        return self._metadata_call(
            load,
            context="provider collection metadata is invalid",
        )

    def get_collection(self, collection_id: str) -> dict[str, Any]:
        client = self._client()
        collection = self._metadata_call(
            lambda: client.get_collection(collection_id),
            context=f"collection {collection_id!r} metadata is invalid",
        )
        if collection is None:
            raise ProviderProtocolError(
                f"provider did not return collection {collection_id!r}",
                status_code=404,
            )

        return _record_dict(
            collection,
            context=f"collection {collection_id!r} metadata is invalid",
        )

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
        client = self._client()
        search = self._provider_call(
            lambda: client.search(
                collections=[collection_id],
                intersects=request.geometry,
                datetime=interval,
                max_items=max_items,
            ),
            capability_context="provider does not support the required Item Search operation",
        )

        def load_items() -> list[dict[str, Any]]:
            records = self._provider_call(search.items)
            return [
                _record_dict(item, context="provider Item metadata is invalid")
                for item in records
            ]

        return self._metadata_call(
            load_items,
            context="provider Item metadata is invalid",
        )
