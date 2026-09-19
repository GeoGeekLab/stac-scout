from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .request import DataType


class ConstraintStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


class BandInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str | None = None
    common_name: str | None = None
    description: str | None = None
    center_wavelength: float | None = None
    full_width_half_max: float | None = None
    unit: str | None = None
    scale: float | None = None
    offset: float | None = None
    nodata: float | int | str | None = None


class AssetInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    href: str | None = None
    media_type: str | None = None
    roles: tuple[str, ...] = ()
    title: str | None = None
    bands: tuple[BandInfo, ...] = ()
    size_bytes: int | None = Field(default=None, ge=0)


class DatasetCard(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    catalog_url: str
    collection_id: str
    title: str | None = None
    description: str | None = None
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
    bands: tuple[BandInfo, ...] = ()
    assets: tuple[AssetInfo, ...] = ()
    source: dict[str, Any] = Field(default_factory=dict)

    @property
    def measurements(self) -> frozenset[str]:
        values: set[str] = set()
        for band in self.bands:
            if band.name:
                values.add(band.name.casefold())
            if band.common_name:
                values.add(band.common_name.casefold())
        for asset in self.assets:
            values.add(asset.key.casefold())
            for band in asset.bands:
                if band.name:
                    values.add(band.name.casefold())
                if band.common_name:
                    values.add(band.common_name.casefold())
        return frozenset(values)


class ConstraintCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    status: ConstraintStatus
    expected: Any = None
    observed: Any = None
    reason: str | None = None
