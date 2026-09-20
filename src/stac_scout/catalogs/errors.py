from __future__ import annotations

from pystac_client.exceptions import APIError


class ProviderError(RuntimeError):
    """Expected failure caused by a remote provider or its published metadata."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class ProviderNetworkError(ProviderError):
    pass


class ProviderTimeoutError(ProviderNetworkError):
    pass


class ProviderAuthenticationError(ProviderError):
    pass


class ProviderRateLimitError(ProviderError):
    pass


class ProviderProtocolError(ProviderError):
    pass


class ProviderMetadataError(ProviderError):
    pass


class ProviderCapabilityError(ProviderError):
    pass


_TIMEOUT_MARKERS = (
    "timed out",
    "timeout",
    "readtimeout",
    "connecttimeout",
)
_NETWORK_MARKERS = (
    "connection",
    "dns",
    "name resolution",
    "network",
    "temporary failure",
    "max retries exceeded",
)


def provider_error_from_api_error(exc: APIError) -> ProviderError:
    status_code = getattr(exc, "status_code", None)
    message = str(exc)
    normalized = message.casefold()

    if status_code in {401, 403}:
        return ProviderAuthenticationError(message, status_code=status_code)
    if status_code == 429:
        return ProviderRateLimitError(
            message,
            status_code=status_code,
            retryable=True,
        )
    if status_code is not None and 500 <= status_code <= 599:
        return ProviderNetworkError(
            message,
            status_code=status_code,
            retryable=True,
        )
    if any(marker in normalized for marker in _TIMEOUT_MARKERS):
        return ProviderTimeoutError(message, retryable=True)
    if any(marker in normalized for marker in _NETWORK_MARKERS):
        return ProviderNetworkError(message, retryable=True)
    return ProviderProtocolError(message, status_code=status_code)
