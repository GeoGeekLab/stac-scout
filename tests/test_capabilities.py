from __future__ import annotations

import httpx
import pytest

import stac_scout.catalogs.capabilities as capabilities_module
from stac_scout.catalogs import (
    ProviderAuthenticationError,
    ProviderMetadataError,
    ProviderNetworkPolicy,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from stac_scout.catalogs.capabilities import inspect_catalog


def test_inspect_catalog_reads_conformance_link() -> None:
    def handler(scout_request: httpx.Request) -> httpx.Response:
        if scout_request.url.path == "/stac":
            return httpx.Response(
                200,
                json={
                    "stac_version": "1.0.0",
                    "links": [
                        {"rel": "search", "href": "https://example.test/stac/search"},
                        {"rel": "conformance", "href": "https://example.test/conformance"},
                    ],
                },
            )
        return httpx.Response(
            200,
            json={
                "conformsTo": [
                    "https://api.stacspec.org/v1.0.0/item-search",
                    "https://api.stacspec.org/v1.0.0/item-search#filter",
                    "https://api.stacspec.org/v1.0.0/item-search#sort",
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = inspect_catalog("https://example.test/stac", client=client)

    assert result.item_search is True
    assert result.filter is True
    assert result.sort is True
    assert result.fields is False
    assert result.stac_version == "1.0.0"


def test_inspect_catalog_rejects_non_object_root() -> None:
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[]))
        ) as client,
        pytest.raises(ProviderMetadataError, match="non-object JSON"),
    ):
        inspect_catalog("https://example.test/stac", client=client)


def test_inspect_catalog_rejects_malformed_links() -> None:
    with (
        httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={"stac_version": "1.0.0", "links": "not-a-list"},
                )
            )
        ) as client,
        pytest.raises(ProviderMetadataError, match="links must be an array"),
    ):
        inspect_catalog("https://example.test/stac", client=client)


def test_inspect_catalog_retries_rate_limit_and_caps_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "999"})
        return httpx.Response(
            200,
            json={
                "stac_version": "1.0.0",
                "conformsTo": ["https://api.stacspec.org/v1.0.0/item-search"],
                "links": [],
            },
        )

    monkeypatch.setattr(capabilities_module.time, "sleep", sleeps.append)
    policy = ProviderNetworkPolicy(
        max_retries=1,
        backoff_jitter_s=0,
        max_retry_delay_s=2.0,
    )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = inspect_catalog(
            "https://example.test/stac",
            client=client,
            network_policy=policy,
        )

    assert result.item_search is True
    assert calls == 2
    assert sleeps == [2.0]


def test_inspect_catalog_raises_rate_limit_after_retry_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"Retry-After": "0"})

    monkeypatch.setattr(capabilities_module.time, "sleep", sleeps.append)
    policy = ProviderNetworkPolicy(max_retries=1, backoff_jitter_s=0)

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ProviderRateLimitError) as exc_info,
    ):
        inspect_catalog(
            "https://example.test/stac",
            client=client,
            network_policy=policy,
        )

    assert calls == 2
    assert sleeps == [0.0]
    assert exc_info.value.status_code == 429
    assert exc_info.value.retryable is True


def test_inspect_catalog_retries_timeout_then_raises_typed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("slow provider", request=request)

    monkeypatch.setattr(capabilities_module.time, "sleep", sleeps.append)
    policy = ProviderNetworkPolicy(
        max_retries=1,
        backoff_factor_s=0.25,
        backoff_jitter_s=0,
    )

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ProviderTimeoutError, match="slow provider") as exc_info,
    ):
        inspect_catalog(
            "https://example.test/stac",
            client=client,
            network_policy=policy,
        )

    assert calls == 2
    assert sleeps == [0.25]
    assert exc_info.value.retryable is True


def test_inspect_catalog_does_not_retry_authentication_failure() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401)

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ProviderAuthenticationError) as exc_info,
    ):
        inspect_catalog(
            "https://example.test/stac",
            client=client,
            network_policy=ProviderNetworkPolicy(max_retries=2),
        )

    assert calls == 1
    assert exc_info.value.status_code == 401
    assert exc_info.value.retryable is False


def test_inspect_catalog_classifies_exhausted_http_408_as_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []

    monkeypatch.setattr(capabilities_module.time, "sleep", sleeps.append)
    policy = ProviderNetworkPolicy(
        max_retries=1,
        backoff_factor_s=0,
        backoff_jitter_s=0,
    )

    transport = httpx.MockTransport(lambda request: httpx.Response(408))
    with (
        httpx.Client(transport=transport) as client,
        pytest.raises(ProviderTimeoutError) as exc_info,
    ):
        inspect_catalog(
            "https://example.test/stac",
            client=client,
            network_policy=policy,
        )

    assert sleeps == [0.0]
    assert exc_info.value.status_code == 408
    assert exc_info.value.retryable is True
