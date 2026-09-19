from __future__ import annotations

import httpx

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
