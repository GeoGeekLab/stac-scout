from __future__ import annotations

from datetime import datetime as DateTime

from pydantic import BaseModel, ConfigDict, Field

from .report import VerificationStatus


class ItemEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str
    datetime: DateTime | None = None
    coverage_ratio: float | None = Field(default=None, ge=0, le=1)
    item_fraction_read: float | None = Field(default=None, ge=0, le=1)
    cloud_cover: float | None = Field(default=None, ge=0, le=100)
    asset_keys: tuple[str, ...] = ()


class AvailabilityProbe(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: VerificationStatus
    items_checked: int = Field(ge=0)
    max_coverage_ratio: float | None = Field(default=None, ge=0, le=1)
    items: tuple[ItemEvidence, ...] = ()
    warnings: tuple[str, ...] = ()
