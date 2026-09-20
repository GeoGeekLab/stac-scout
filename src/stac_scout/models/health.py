from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ProviderHealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNREACHABLE = "unreachable"


class ProviderHealth(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_key: str
    url: str
    status: ProviderHealthStatus
    checked_at: datetime
    latency_ms: float | None = Field(default=None, ge=0)
    stac_version: str | None = None
    item_search: bool | None = None
    error_type: str | None = None
    error: str | None = None
    status_code: int | None = None
    retryable: bool | None = None
