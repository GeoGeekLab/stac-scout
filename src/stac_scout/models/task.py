from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .request import DataType


class GeoTask(StrEnum):
    VEGETATION_CONDITION = "vegetation_condition"
    WILDFIRE_IMPACT = "wildfire_impact"
    FLOOD_EXTENT = "flood_extent"
    SURFACE_WATER = "surface_water"
    SNOW_COVER = "snow_cover"
    LAND_COVER_CHANGE = "land_cover_change"
    URBAN_CHANGE = "urban_change"
    TERRAIN = "terrain"


class TemporalStrategy(StrEnum):
    SINGLE_WINDOW = "single_window"
    BEFORE_AFTER = "before_after"
    TIME_SERIES = "time_series"
    STATIC = "static"


class RequirementStrength(StrEnum):
    REQUIRED = "required"
    PREFERRED = "preferred"


class TaskProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_type: GeoTask
    label: str = Field(min_length=1)
    rule_id: str = Field(min_length=1)
    data_type: DataType
    temporal_strategy: TemporalStrategy
    required_measurements: tuple[str, ...] = ()
    preferred_measurements: tuple[str, ...] = ()
    preferred_processing_levels: tuple[str, ...] = ()
    preferred_masks: tuple[str, ...] = ()
    rationale: str = Field(min_length=1)
    sources: tuple[str, ...] = ()


class DerivedRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str
    field: str
    value: Any
    strength: RequirementStrength
    rationale: str
