from __future__ import annotations

import pytest
from pystac_client.exceptions import APIError

from stac_scout.catalogs import (
    ProviderAuthenticationError,
    ProviderMetadataError,
    ProviderNetworkError,
    ProviderNetworkPolicy,
    ProviderProtocolError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from stac_scout.catalogs.errors import provider_error_from_api_error


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"connect_timeout_s": 0}, "connect_timeout_s"),
        ({"read_timeout_s": 0}, "read_timeout_s"),
        ({"max_retries": -1}, "max_retries"),
        ({"backoff_factor_s": -1}, "backoff_factor_s"),
        ({"backoff_jitter_s": -1}, "backoff_jitter_s"),
    ],
)
def test_network_policy_rejects_invalid_values(
    kwargs: dict[str, float | int],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        ProviderNetworkPolicy(**kwargs)


def test_network_policy_builds_bounded_retry_configuration() -> None:
    policy = ProviderNetworkPolicy(
        max_retries=2,
        backoff_factor_s=0.25,
        backoff_jitter_s=0.1,
    )

    retry = policy.retry()

    assert policy.timeout == (5.0, 20.0)
    assert retry.total == 2
    assert retry.connect == 2
    assert retry.read == 2
    assert retry.status == 2
    assert retry.status_forcelist == (429, 502, 503, 504)
    assert retry.allowed_methods is None
    assert retry.respect_retry_after_header is True


def _api_error(message: str, status_code: int | None = None) -> APIError:
    exc = APIError(message)
    exc.status_code = status_code
    return exc


@pytest.mark.parametrize(
    ("exc", "expected_type", "retryable"),
    [
        (_api_error("unauthorized", 401), ProviderAuthenticationError, False),
        (_api_error("forbidden", 403), ProviderAuthenticationError, False),
        (_api_error("rate limited", 429), ProviderRateLimitError, True),
        (_api_error("upstream unavailable", 503), ProviderNetworkError, True),
        (_api_error("read timed out"), ProviderTimeoutError, True),
        (_api_error("connection aborted"), ProviderNetworkError, True),
        (_api_error("bad request", 400), ProviderProtocolError, False),
    ],
)
def test_api_errors_map_to_typed_provider_failures(
    exc: APIError,
    expected_type: type[Exception],
    retryable: bool,
) -> None:
    mapped = provider_error_from_api_error(exc)

    assert isinstance(mapped, expected_type)
    assert mapped.retryable is retryable
    assert mapped.status_code == exc.status_code


def test_provider_metadata_error_is_not_marked_retryable() -> None:
    error = ProviderMetadataError("bad catalog metadata")

    assert error.retryable is False
    assert error.status_code is None
