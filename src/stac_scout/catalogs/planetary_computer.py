from __future__ import annotations

from collections.abc import Callable
from typing import Any

from stac_scout.models import AssetSigning

from .generic import GenericStacAdapter
from .network import ProviderNetworkPolicy


class PlanetaryComputerAdapter(GenericStacAdapter):
    def __init__(
        self,
        catalog_url: str,
        *,
        provider_key: str = "planetary-computer",
        client_factory: Callable[[str], Any] | None = None,
        network_policy: ProviderNetworkPolicy | None = None,
    ) -> None:
        super().__init__(
            catalog_url,
            provider_key=provider_key,
            asset_signing=AssetSigning.PLANETARY_COMPUTER,
            client_factory=client_factory,
            network_policy=network_policy,
        )
