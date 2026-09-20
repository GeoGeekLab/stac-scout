from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .catalog import CatalogCapabilities
from .dataset import BandInfo, ConstraintCheck
from .provider import AssetSigning
from .request import DataType, ScoutRequest


class VerificationStatus(StrEnum):
    VERIFIED_AVAILABLE = "verified_available"
    VERIFIED_EMPTY = "verified_empty"
    INCONCLUSIVE = "inconclusive"
    UNVERIFIED = "unverified"


class SearchCompleteness(StrEnum):
    COMPLETE = "complete"
    LIMIT_REACHED = "limit_reached"
    UNKNOWN = "unknown"


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    claim: str
    value: Any
    observed_at: datetime


class AssetChoice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    measurement: str
    asset_key: str
    match_basis: str
    selection_reason: str
    gsd_m: float | None = Field(default=None, gt=0)
    gsd_complete: bool = False
    item_coverage_complete: bool = False
    resampling: str | None = None
    resampling_basis: str | None = None


class AccessPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy: str
    assets: tuple[str, ...] = ()
    asset_choices: tuple[AssetChoice, ...] = ()
    estimated_bytes: int | None = Field(default=None, ge=0)
    output_crs: str | None = None
    output_resolution: float | None = Field(default=None, gt=0)
    resampling: dict[str, str] = Field(default_factory=dict)
    constraints: tuple[ConstraintCheck, ...] = ()
    notes: tuple[str, ...] = ()


class SearchObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_items: int | None = Field(default=None, ge=1)
    returned_items: int = Field(ge=0)
    accepted_items: int = Field(ge=0)
    completeness: SearchCompleteness
    pagination_mode: str = "provider-managed"
    ordering: str = "provider-default"

    @model_validator(mode="after")
    def validate_counts(self) -> SearchObservation:
        if self.accepted_items > self.returned_items:
            raise ValueError("accepted_items must not exceed returned_items")
        if self.completeness is SearchCompleteness.COMPLETE and self.max_items is not None:
            if self.returned_items >= self.max_items:
                raise ValueError(
                    "complete search must return fewer Items than the recorded max_items"
                )
        if self.completeness is SearchCompleteness.LIMIT_REACHED:
            if self.max_items is None or self.returned_items != self.max_items:
                raise ValueError(
                    "limit_reached search must return exactly the recorded max_items"
                )
        return self


class CollectionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    collection_id: str
    title: str | None = None
    doi: str | None = None
    data_type: DataType | None = None
    providers: tuple[str, ...] = ()
    platforms: tuple[str, ...] = ()
    constellations: tuple[str, ...] = ()
    instruments: tuple[str, ...] = ()
    license: str | None = None
    spatial_extent: tuple[float, float, float, float] | None = None
    temporal_start: datetime | None = None
    temporal_end: datetime | None = None
    spatial_resolution_m: float | None = Field(default=None, gt=0)
    measurements: tuple[str, ...] = ()


class AssetMetadataSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str
    asset_key: str
    media_type: str | None = None
    roles: tuple[str, ...] = ()
    title: str | None = None
    bands: tuple[BandInfo, ...] = ()
    size_bytes: int | None = Field(default=None, ge=0)
    gsd_m: float | None = Field(default=None, gt=0)


class CandidateAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    catalog_url: str
    collection_id: str
    status: VerificationStatus = VerificationStatus.UNVERIFIED
    hard_constraints_passed: bool | None = None
    score: float | None = Field(default=None, ge=0, le=1)
    evidence: tuple[Evidence, ...] = ()
    caveats: tuple[str, ...] = ()


class DecisionReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request: ScoutRequest
    recommendation: CandidateAssessment | None = None
    alternatives: tuple[CandidateAssessment, ...] = ()
    access_plan: AccessPlan | None = None
    generated_at: datetime


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    scout_version: str
    generated_at: datetime
    request: ScoutRequest
    catalog_url: str
    collection_id: str
    provider_key: str | None = None
    asset_signing: AssetSigning = AssetSigning.NONE
    catalog_capabilities: CatalogCapabilities | None = None
    collection_snapshot: CollectionSnapshot | None = None
    collection_fingerprint_sha256: str | None = None
    query: dict[str, Any]
    search: SearchObservation
    access_plan: AccessPlan | None = None
    item_ids: tuple[str, ...] = ()
    asset_keys: tuple[str, ...] = ()
    asset_metadata: tuple[AssetMetadataSnapshot, ...] = ()
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
