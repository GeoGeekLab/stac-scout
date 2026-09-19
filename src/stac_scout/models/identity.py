from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class IdentityStrength(StrEnum):
    EXACT = "exact"
    PROBABLE = "probable"
    LOCAL = "local"


class DatasetIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(min_length=1)
    strength: IdentityStrength
    basis: tuple[str, ...] = ()
