from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

from stac_scout.models import CatalogCapabilities, ScoutRequest


class CatalogAdapter(Protocol):
    catalog_url: str

    def inspect(self) -> CatalogCapabilities: ...

    def list_collections(self) -> Iterable[dict[str, Any]]: ...

    def get_collection(self, collection_id: str) -> dict[str, Any]: ...

    def search_items(
        self,
        request: ScoutRequest,
        collection_id: str,
        *,
        max_items: int = 100,
    ) -> list[dict[str, Any]]: ...
