from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ProviderAdapter(StrEnum):
    GENERIC = "generic"
    PLANETARY_COMPUTER = "planetary_computer"


class ProviderAccess(StrEnum):
    OPEN = "open"
    AUTHENTICATED = "authenticated"
    MIXED = "mixed"


class AssetSigning(StrEnum):
    NONE = "none"
    PLANETARY_COMPUTER = "planetary_computer"
    PROVIDER_DEPENDENT = "provider_dependent"


class ProviderSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    url: str = Field(min_length=1)
    adapter: ProviderAdapter = ProviderAdapter.GENERIC
    access: ProviderAccess = ProviderAccess.OPEN
    asset_signing: AssetSigning = AssetSigning.NONE
    enabled: bool = True
    notes: str | None = None
