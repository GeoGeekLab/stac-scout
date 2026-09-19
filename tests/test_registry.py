from __future__ import annotations

import pytest

from stac_scout.models import AssetSigning, ProviderAdapter
from stac_scout.registry import ProviderRegistry, UnknownProviderError


def test_builtin_registry_exposes_enabled_providers() -> None:
    registry = ProviderRegistry.builtin()

    providers = registry.all()

    assert [provider.key for provider in providers] == ["earth-search", "planetary-computer"]
    planetary = registry.get("planetary-computer")
    assert planetary.adapter is ProviderAdapter.PLANETARY_COMPUTER
    assert planetary.asset_signing is AssetSigning.PLANETARY_COMPUTER


def test_builtin_registry_keeps_disabled_provider_metadata() -> None:
    registry = ProviderRegistry.builtin()

    providers = registry.all(include_disabled=True)

    assert [provider.key for provider in providers] == [
        "earth-search",
        "nasa-cmr",
        "planetary-computer",
    ]
    assert registry.get("nasa-cmr").enabled is False


def test_registry_rejects_unknown_provider() -> None:
    with pytest.raises(UnknownProviderError):
        ProviderRegistry.builtin().get("missing")


def test_registry_select_deduplicates_requested_keys() -> None:
    selected = ProviderRegistry.builtin().select(["earth-search", "earth-search"])

    assert [provider.key for provider in selected] == ["earth-search"]


def test_registry_requires_provider_table() -> None:
    with pytest.raises(ValueError, match="providers table"):
        ProviderRegistry.from_mapping({})
