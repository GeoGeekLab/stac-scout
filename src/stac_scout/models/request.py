from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DataType(StrEnum):
    OPTICAL = "optical"
    SAR = "sar"
    ELEVATION = "elevation"
    LAND_COVER = "land_cover"
    WEATHER = "weather"
    CLIMATE = "climate"
    VECTOR = "vector"
    ANY = "any"


class AccessPolicy(StrEnum):
    OPEN = "open"
    FREE = "free"
    ANY = "any"


class TimeRange(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    start: datetime
    end: datetime

    @model_validator(mode="after")
    def validate_order(self) -> TimeRange:
        if self.end < self.start:
            raise ValueError("end must not be earlier than start")
        return self


class ScoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task: str = Field(min_length=1)
    geometry: dict[str, Any] | None = None
    place: str | None = None
    datetime: TimeRange
    data_type: DataType = DataType.ANY
    required_measurements: tuple[str, ...] = ()
    max_spatial_resolution_m: float | None = Field(default=None, gt=0)
    max_cloud_cover: float | None = Field(default=None, ge=0, le=100)
    access: AccessPolicy = AccessPolicy.ANY
    max_data_volume_bytes: int | None = Field(default=None, gt=0)
    preferences: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_location(self) -> ScoutRequest:
        if self.geometry is None and self.place is None:
            raise ValueError("either geometry or place must be provided")
        return self
