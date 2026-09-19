from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import httpx

from stac_scout.models import CatalogCapabilities


def _supports(classes: Iterable[str], fragment: str) -> bool:
    needle = fragment.casefold()
    return any(needle in value.casefold() for value in classes)


def _conformance_href(root: dict[str, Any]) -> str | None:
    for link in root.get("links", []):
        if link.get("rel") == "conformance" and isinstance(link.get("href"), str):
            return link["href"]
    return None


def inspect_catalog(
    url: str,
    *,
    client: httpx.Client | None = None,
    timeout: float = 20.0,
) -> CatalogCapabilities:
    owned_client = client is None
    http = client or httpx.Client(timeout=timeout, follow_redirects=True)
    try:
        root_response = http.get(url)
        root_response.raise_for_status()
        root = root_response.json()

        classes = set(root.get("conformsTo", []))
        conformance_url = _conformance_href(root)
        if conformance_url:
            response = http.get(conformance_url)
            response.raise_for_status()
            classes.update(response.json().get("conformsTo", []))

        links = root.get("links", [])
        has_search_link = any(link.get("rel") == "search" for link in links)

        ordered = tuple(sorted(str(value) for value in classes))
        return CatalogCapabilities(
            url=url,
            stac_version=root.get("stac_version"),
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
