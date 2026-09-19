from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .provider import AssetSigning
from .request import ScoutRequest


class VerificationStatus(StrEnum):
    VERIFIED_AVAILABLE = "verified_available"
    VERIFIED_EMPTY = "verified_empty"
    INCONCLUSIVE = "inconclusive"
    UNVERIFIED = "unverified"


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    claim: str
    value: Any
    observed_at: datetime


class AccessPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy: str
    assets: tuple[str, ...] = ()
    estimated_bytes: int | None = Field(default=None, ge=0)
    output_crs: str | None = None
    output_resolution: float | None = Field(default=None, gt=0)
    resampling: dict[str, str] = Field(default_factory=dict)
    notes: tuple[str, ...] = ()


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

    scout_version: str
    generated_at: datetime
    request: ScoutRequest
    catalog_url: str
    collection_id: str
    provider_key: str | None = None
    asset_signing: AssetSigning = AssetSigning.NONE
    query: dict[str, Any]
    item_ids: tuple[str, ...] = ()
    asset_keys: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
