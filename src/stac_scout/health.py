from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from time import perf_counter

import httpx

from stac_scout.catalogs.capabilities import inspect_catalog
from stac_scout.catalogs.errors import ProviderError
from stac_scout.catalogs.network import ProviderNetworkPolicy
from stac_scout.models import ProviderHealth, ProviderHealthStatus, ProviderSpec


def check_provider(
    provider: ProviderSpec,
    *,
    client: httpx.Client | None = None,
    timeout: float = 10.0,
    network_policy: ProviderNetworkPolicy | None = None,
    now: Callable[[], datetime] | None = None,
    clock: Callable[[], float] = perf_counter,
) -> ProviderHealth:
    checked_at = (now or (lambda: datetime.now(UTC)))()
    started = clock()
    try:
        capabilities = inspect_catalog(
            provider.url,
            client=client,
            timeout=timeout,
            network_policy=network_policy,
        )
    except ProviderError as exc:
        elapsed = max(0.0, (clock() - started) * 1000)
        return ProviderHealth(
            provider_key=provider.key,
            url=provider.url,
            status=ProviderHealthStatus.UNREACHABLE,
            checked_at=checked_at,
            latency_ms=elapsed,
            error_type=type(exc).__name__,
            error=str(exc),
        )

    elapsed = max(0.0, (clock() - started) * 1000)
    status = (
        ProviderHealthStatus.HEALTHY if capabilities.item_search else ProviderHealthStatus.DEGRADED
    )
    return ProviderHealth(
        provider_key=provider.key,
        url=provider.url,
        status=status,
        checked_at=checked_at,
        latency_ms=elapsed,
        stac_version=capabilities.stac_version,
        item_search=capabilities.item_search,
    )


def check_providers(
    providers: Iterable[ProviderSpec],
    *,
    timeout: float = 10.0,
    network_policy: ProviderNetworkPolicy | None = None,
) -> tuple[ProviderHealth, ...]:
    return tuple(
        check_provider(
            provider,
            timeout=timeout,
            network_policy=network_policy,
        )
        for provider in providers
    )
