from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .request import AccessPolicy, DataType, ScoutRequest, TimeRange
from .task import GeoTask


class UnresolvedIntentError(ValueError):
    pass


class IntentDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task: str = Field(min_length=1)
    task_type: GeoTask | None = None
    geometry: dict[str, Any] | None = None
    place: str | None = None
    datetime: TimeRange | None = None
    data_type: DataType = DataType.ANY
    required_measurements: tuple[str, ...] = ()
    max_source_resolution_m: float | None = Field(default=None, gt=0)
    target_crs: str | None = Field(default=None, min_length=1)
    target_resolution_m: float | None = Field(default=None, gt=0)
    max_cloud_cover: float | None = Field(default=None, ge=0, le=100)
    access: AccessPolicy = AccessPolicy.ANY
    max_data_volume_bytes: int | None = Field(default=None, gt=0)
    preferences: dict[str, Any] = Field(default_factory=dict)
    assumptions: tuple[str, ...] = ()
    unresolved: tuple[str, ...] = ()

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

    def to_request(self) -> ScoutRequest:
        missing = list(self.unresolved)
        if self.datetime is None:
            missing.append("datetime")
        if self.geometry is None and self.place is None:
            missing.append("location")
        if missing:
            unique = ", ".join(dict.fromkeys(missing))
            raise UnresolvedIntentError(f"intent is unresolved: {unique}")

        if self.datetime is None:
            raise AssertionError("datetime validation should have rejected an unresolved intent")

        return ScoutRequest(
            task=self.task,
            geometry=self.geometry,
            place=self.place,
            datetime=self.datetime,
            data_type=self.data_type,
            required_measurements=self.required_measurements,
            max_source_resolution_m=self.max_source_resolution_m,
            target_crs=self.target_crs,
            target_resolution_m=self.target_resolution_m,
            max_cloud_cover=self.max_cloud_cover,
            access=self.access,
            max_data_volume_bytes=self.max_data_volume_bytes,
            preferences=self.preferences,
        )
