from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from math import isclose, isfinite
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pyproj import CRS
from pyproj.exceptions import CRSError
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
    max_source_resolution_m: float | None = Field(default=None, gt=0)
    target_crs: str | None = Field(default=None, min_length=1)
    target_resolution_m: float | None = Field(default=None, gt=0)
    max_cloud_cover: float | None = Field(default=None, ge=0, le=100)
    access: AccessPolicy = AccessPolicy.ANY
    max_data_volume_bytes: int | None = Field(default=None, gt=0)
    preferences: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_resolution_field(cls, value: Any) -> Any:
        if not isinstance(value, dict) or "max_spatial_resolution_m" not in value:
            return value
        if "max_source_resolution_m" in value:
            raise ValueError(
                "use only max_source_resolution_m; do not also provide "
                "legacy max_spatial_resolution_m"
            )
        migrated = dict(value)
        migrated["max_source_resolution_m"] = migrated.pop("max_spatial_resolution_m")
        return migrated

    @property
    def max_spatial_resolution_m(self) -> float | None:
        """Backward-compatible read alias for the source-resolution constraint."""
        return self.max_source_resolution_m

    @field_validator("target_crs")
    @classmethod
    def validate_target_crs(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        if normalized.casefold() == "utm":
            return "utm"

        try:
            CRS.from_user_input(normalized)
        except CRSError as exc:
            raise ValueError("target_crs must be a valid CRS or 'utm'") from exc
        return normalized

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
    def validate_target_grid(self) -> ScoutRequest:
        if self.target_resolution_m is None:
            return self
        if self.target_crs is None:
            raise ValueError("target_crs is required when target_resolution_m is set")
        if self.target_crs == "utm":
            return self

        crs = CRS.from_user_input(self.target_crs)
        if not crs.is_projected:
            raise ValueError("target_resolution_m requires a projected meter-based target_crs")

        horizontal_axes = crs.axis_info[:2]
        if not horizontal_axes or any(
            axis.unit_conversion_factor is None
            or not isclose(float(axis.unit_conversion_factor), 1.0, rel_tol=0.0, abs_tol=1e-12)
            for axis in horizontal_axes
        ):
            raise ValueError("target_resolution_m requires a projected meter-based target_crs")
        return self

    @model_validator(mode="after")
    def validate_location(self) -> ScoutRequest:
        if self.geometry is None and self.place is None:
            raise ValueError("either geometry or place must be provided")
        return self
