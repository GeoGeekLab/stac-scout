from __future__ import annotations

from collections.abc import Callable
from typing import Any, assert_never

from stac_scout.models import ProviderAdapter, ProviderSpec

from .base import CatalogAdapter
from .generic import GenericStacAdapter
from .network import ProviderNetworkPolicy
from .planetary_computer import PlanetaryComputerAdapter


def build_adapter(
    provider: ProviderSpec,
    *,
    client_factory: Callable[[str], Any] | None = None,
    network_policy: ProviderNetworkPolicy | None = None,
) -> CatalogAdapter:
    match provider.adapter:
        case ProviderAdapter.GENERIC:
            return GenericStacAdapter(
                provider.url,
                provider_key=provider.key,
                asset_signing=provider.asset_signing,
                client_factory=client_factory,
                network_policy=network_policy,
            )
        case ProviderAdapter.PLANETARY_COMPUTER:
            return PlanetaryComputerAdapter(
                provider.url,
                provider_key=provider.key,
                client_factory=client_factory,
                network_policy=network_policy,
            )
    assert_never(provider.adapter)
