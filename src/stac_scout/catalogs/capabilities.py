from __future__ import annotations

import random
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from stac_scout.models import CatalogCapabilities

from .errors import (
    ProviderAuthenticationError,
    ProviderMetadataError,
    ProviderNetworkError,
    ProviderProtocolError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from .network import ProviderNetworkPolicy


def _supports(classes: Iterable[str], fragment: str) -> bool:
    needle = fragment.casefold()
    return any(needle in value.casefold() for value in classes)


def _links(root: dict[str, Any], *, context: str) -> list[dict[str, Any]]:
    raw = root.get("links", [])
    if not isinstance(raw, list):
        raise ProviderMetadataError(f"{context} links must be an array")
    if not all(isinstance(link, dict) for link in raw):
        raise ProviderMetadataError(f"{context} links must contain objects")
    return raw


def _conformance_href(root: dict[str, Any]) -> str | None:
    for link in _links(root, context="catalog root"):
        if link.get("rel") != "conformance":
            continue
        href = link.get("href")
        if isinstance(href, str):
            return href
        raise ProviderMetadataError("conformance link href must be a string")
    return None


def _conformance_classes(document: dict[str, Any], *, context: str) -> set[str]:
    raw = document.get("conformsTo", [])
    if not isinstance(raw, list) or not all(isinstance(value, str) for value in raw):
        raise ProviderMetadataError(f"{context} conformsTo must be an array of strings")
    return set(raw)


def _retry_after_seconds(value: str | None) -> float | None:
    if value is None:
        return None
    stripped = value.strip()
    try:
        seconds = float(stripped)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(stripped)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())
    return max(0.0, seconds)


def _backoff_seconds(policy: ProviderNetworkPolicy, attempt: int) -> float:
    base: float = policy.backoff_factor_s * (2**attempt)
    jitter: float = float(random.uniform(0.0, policy.backoff_jitter_s))
    delay: float = base + jitter
    if delay > policy.max_retry_delay_s:
        return policy.max_retry_delay_s
    return delay


def _raise_response_error(response: httpx.Response) -> None:
    status = response.status_code
    message = f"provider returned HTTP {status} for {response.request.url}"
    if status in {401, 403}:
        raise ProviderAuthenticationError(message, status_code=status)
    if status == 408:
        raise ProviderTimeoutError(message, status_code=status, retryable=True)
    if status == 429:
        raise ProviderRateLimitError(message, status_code=status, retryable=True)
    if 500 <= status <= 599:
        raise ProviderNetworkError(message, status_code=status, retryable=True)
    raise ProviderProtocolError(message, status_code=status)


def _get_json_object(
    http: httpx.Client,
    url: str,
    *,
    policy: ProviderNetworkPolicy,
) -> dict[str, Any]:
    response: httpx.Response | None = None
    for attempt in range(policy.max_retries + 1):
        try:
            response = http.get(url)
        except httpx.TimeoutException as exc:
            if attempt < policy.max_retries:
                time.sleep(_backoff_seconds(policy, attempt))
                continue
            raise ProviderTimeoutError(str(exc), retryable=True) from exc
        except httpx.RequestError as exc:
            if attempt < policy.max_retries:
                time.sleep(_backoff_seconds(policy, attempt))
                continue
            raise ProviderNetworkError(str(exc), retryable=True) from exc

        if 200 <= response.status_code <= 299:
            break

        if response.status_code in policy.retry_statuses and attempt < policy.max_retries:
            retry_after = _retry_after_seconds(response.headers.get("Retry-After"))
            delay = (
                min(retry_after, policy.max_retry_delay_s)
                if retry_after is not None
                else _backoff_seconds(policy, attempt)
            )
            time.sleep(delay)
            continue

        _raise_response_error(response)

    if response is None:
        raise AssertionError("provider request loop completed without a response")

    try:
        payload = response.json()
    except ValueError as exc:
        raise ProviderMetadataError(f"provider returned invalid JSON for {url}") from exc
    if not isinstance(payload, dict):
        raise ProviderMetadataError(f"provider returned a non-object JSON document for {url}")
    return payload


def inspect_catalog(
    url: str,
    *,
    client: httpx.Client | None = None,
    timeout: float = 20.0,
    network_policy: ProviderNetworkPolicy | None = None,
) -> CatalogCapabilities:
    policy = network_policy or ProviderNetworkPolicy(
        connect_timeout_s=timeout,
        read_timeout_s=timeout,
    )
    owned_client = client is None
    http = client or httpx.Client(
        timeout=httpx.Timeout(
            connect=policy.connect_timeout_s,
            read=policy.read_timeout_s,
            write=policy.read_timeout_s,
            pool=policy.connect_timeout_s,
        ),
        follow_redirects=True,
    )
    try:
        root = _get_json_object(http, url, policy=policy)
        classes = _conformance_classes(root, context="catalog root")

        conformance_url = _conformance_href(root)
        if conformance_url:
            document = _get_json_object(http, conformance_url, policy=policy)
            classes.update(_conformance_classes(document, context="conformance document"))

        links = _links(root, context="catalog root")
        has_search_link = any(link.get("rel") == "search" for link in links)
        stac_version = root.get("stac_version")
        if stac_version is not None and not isinstance(stac_version, str):
            raise ProviderMetadataError("catalog root stac_version must be a string")

        ordered = tuple(sorted(classes))
        return CatalogCapabilities(
            url=url,
            stac_version=stac_version,
            conformance_classes=ordered,
            item_search=has_search_link or _supports(ordered, "item-search"),
            collection_search=_supports(ordered, "collection-search"),
            query=_supports(ordered, "#query"),
            filter=_supports(ordered, "#filter"),
            sort=_supports(ordered, "#sort"),
            fields=_supports(ordered, "#fields"),
        )
    finally:
        if owned_client:
            http.close()
