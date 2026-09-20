from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from math import isfinite
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from shapely.errors import GEOSException
from shapely.geometry import shape


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

    @field_validator("start", "end")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime values must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_order(self) -> TimeRange:
        if self.end < self.start:
            raise ValueError("end must not be earlier than start")
        return self


class ScoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task: str = Field(min_length=1)
    geometry: dict[str, Any] | None = None
    place: str | None = Field(default=None, min_length=1)
    datetime: TimeRange
    data_type: DataType = DataType.ANY
    required_measurements: tuple[str, ...] = ()
    max_spatial_resolution_m: float | None = Field(default=None, gt=0)
    max_cloud_cover: float | None = Field(default=None, ge=0, le=100)
    access: AccessPolicy = AccessPolicy.ANY
    max_data_volume_bytes: int | None = Field(default=None, gt=0)
    preferences: dict[str, Any] = Field(default_factory=dict)

    @field_validator("geometry")
    @classmethod
    def validate_geometry(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return None

        geometry_type = value.get("type")
        if geometry_type not in {"Polygon", "MultiPolygon"}:
            raise ValueError("geometry must be a GeoJSON Polygon or MultiPolygon")

        try:
            geometry = shape(value)
        except (GEOSException, KeyError, TypeError, ValueError) as exc:
            raise ValueError("geometry is not valid GeoJSON") from exc

        if geometry.is_empty:
            raise ValueError("geometry must not be empty")
        if not geometry.is_valid:
            raise ValueError("geometry must be topologically valid")

        west, south, east, north = geometry.bounds
        if not all(isfinite(value) for value in (west, south, east, north)):
            raise ValueError("geometry coordinates must be finite")
        if west < -180 or east > 180 or south < -90 or north > 90:
            raise ValueError("geometry coordinates must use WGS84 longitude/latitude bounds")

        return value

    @field_validator("required_measurements")
    @classmethod
    def normalize_measurements(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            measurement = value.strip()
            if not measurement:
                raise ValueError("required measurements must not be empty")
            key = measurement.casefold()
            if key in seen:
                continue
            normalized.append(measurement)
            seen.add(key)
        return tuple(normalized)

    @model_validator(mode="after")
    def validate_location(self) -> ScoutRequest:
        if self.geometry is None and self.place is None:
            raise ValueError("either geometry or place must be provided")
        return self
