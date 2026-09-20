from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .catalog import CatalogCapabilities
from .dataset import DatasetCard
from .probe import ItemEvidence, SearchObservation
from .provider import AssetSigning
from .report import AccessPlan
from .request import ScoutRequest

CURRENT_MANIFEST_SCHEMA_VERSION = "1.0"


class SearchQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    collections: tuple[str, ...] = Field(min_length=1)
    intersects: dict[str, Any]
    datetime: str = Field(min_length=1)
    max_items: int | None = Field(default=None, gt=0)


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    migrated_from_schema_version: str | None = None
    scout_version: str
    generated_at: datetime
    request: ScoutRequest
    request_fingerprint: str = Field(min_length=64, max_length=64)
    catalog_url: str
    collection_id: str
    provider_key: str | None = None
    adapter_type: str | None = None
    asset_signing: AssetSigning = AssetSigning.NONE
    catalog_capabilities: CatalogCapabilities | None = None
    collection_snapshot: DatasetCard | None = None
    collection_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)
    query: SearchQuery
    query_fingerprint: str = Field(min_length=64, max_length=64)
    observation: SearchObservation
    item_ids: tuple[str, ...] = ()
    item_evidence: tuple[ItemEvidence, ...] = ()
    access_plan: AccessPlan | None = None
    asset_keys: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    migration_warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_query_alignment(self) -> Manifest:
        if self.query.collections != (self.collection_id,):
            raise ValueError("manifest query collection does not match collection_id")
        if self.query.intersects != self.request.geometry:
            raise ValueError("manifest query geometry does not match request geometry")

        expected_datetime = f"{self.request.datetime.start.isoformat()}/{self.request.datetime.end.isoformat()}"
        if self.query.datetime != expected_datetime:
            raise ValueError("manifest query datetime does not match request datetime")
        if self.observation.max_items != self.query.max_items:
            raise ValueError("manifest observation limit does not match query max_items")
        if self.observation.items_retained != len(self.item_ids):
            raise ValueError("manifest retained-item count does not match item_ids")
        if self.item_evidence and len(self.item_evidence) != len(self.item_ids):
            raise ValueError("manifest item_evidence count does not match item_ids")
        if self.access_plan is not None and self.asset_keys != self.access_plan.assets:
            raise ValueError("manifest asset_keys do not match access_plan assets")
        return self
