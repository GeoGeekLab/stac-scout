from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CatalogCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str
    stac_version: str | None = None
    conformance_classes: tuple[str, ...] = ()
    item_search: bool = False
    collection_search: bool = False
    query: bool = False
    filter: bool = False
    sort: bool = False
    fields: bool = False
