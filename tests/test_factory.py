from __future__ import annotations

from stac_scout.catalogs import GenericStacAdapter, PlanetaryComputerAdapter, build_adapter
from stac_scout.models import AssetSigning, ProviderAdapter, ProviderSpec


def test_factory_builds_generic_adapter() -> None:
    provider = ProviderSpec(
        key="earth-search",
        name="Earth Search",
        url="https://example.test/stac",
    )

    adapter = build_adapter(provider)

    assert isinstance(adapter, GenericStacAdapter)
    assert adapter.provider_key == "earth-search"
    assert adapter.asset_signing is AssetSigning.NONE


def test_factory_builds_planetary_computer_adapter() -> None:
    provider = ProviderSpec(
        key="planetary-computer",
        name="Planetary Computer",
        url="https://example.test/stac",
        adapter=ProviderAdapter.PLANETARY_COMPUTER,
        asset_signing=AssetSigning.PLANETARY_COMPUTER,
    )

    adapter = build_adapter(provider)

    assert isinstance(adapter, PlanetaryComputerAdapter)
    assert adapter.asset_signing is AssetSigning.PLANETARY_COMPUTER
