from __future__ import annotations

from datetime import UTC, datetime

import httpx

from stac_scout.health import check_provider
from stac_scout.models import ProviderHealthStatus, ProviderSpec


def _provider() -> ProviderSpec:
    return ProviderSpec(
        key="example",
        name="Example",
        url="https://example.test/stac",
    )


def test_health_reports_healthy_item_search() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/stac"
        return httpx.Response(
            200,
            json={
                "stac_version": "1.0.0",
                "conformsTo": ["https://api.stacspec.org/v1.0.0/item-search"],
                "links": [{"rel": "search", "href": "https://example.test/stac/search"}],
            },
        )

    ticks = iter([1.0, 1.125])
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = check_provider(
            _provider(),
            client=client,
            now=lambda: datetime(2026, 9, 19, tzinfo=UTC),
            clock=lambda: next(ticks),
        )

    assert result.status is ProviderHealthStatus.HEALTHY
    assert result.latency_ms == 125.0
    assert result.item_search is True


def test_health_reports_degraded_without_item_search() -> None:
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"stac_version": "1.0.0", "links": []})
        )
    ) as client:
        result = check_provider(_provider(), client=client)

    assert result.status is ProviderHealthStatus.DEGRADED
    assert result.item_search is False


def test_health_reports_unreachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = check_provider(_provider(), client=client)

    assert result.status is ProviderHealthStatus.UNREACHABLE
    assert result.error_type == "ConnectError"
    assert result.error == "offline"
