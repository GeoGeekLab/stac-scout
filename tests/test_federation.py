from __future__ import annotations

from math import inf, nan
from threading import Event
from typing import Any

import pytest

from stac_scout.catalogs import (
    ProviderNetworkError,
    ProviderNetworkPolicy,
    ProviderRateLimitError,
)
from stac_scout.federation import FederatedScout
from stac_scout.models import ScoutRequest
from stac_scout.registry import ProviderRegistry


class Adapter:
    def __init__(self, catalog_url: str, collections: list[dict[str, Any]]) -> None:
        self.catalog_url = catalog_url
        self.collections = collections

    def inspect(self) -> Any:
        raise NotImplementedError

    def list_collections(self) -> list[dict[str, Any]]:
        return self.collections

    def get_collection(self, collection_id: str) -> dict[str, Any]:
        return next(
            collection for collection in self.collections if collection["id"] == collection_id
        )

    def search_items(
        self,
        request: ScoutRequest,
        collection_id: str,
        *,
        max_items: int = 100,
    ) -> list[dict[str, Any]]:
        return []


class ProviderFailureAdapter(Adapter):
    def list_collections(self) -> list[dict[str, Any]]:
        raise ProviderRateLimitError(
            "provider rate limited discovery",
            status_code=429,
            retryable=True,
        )


class ProgrammingBugAdapter(Adapter):
    def list_collections(self) -> list[dict[str, Any]]:
        raise RuntimeError("internal invariant failed")


class SlowAdapter(Adapter):
    def __init__(self, catalog_url: str, release: Event) -> None:
        super().__init__(catalog_url, [])
        self.release = release

    def list_collections(self) -> list[dict[str, Any]]:
        self.release.wait(timeout=1.0)
        return []


def _collection(identifier: str, doi: str) -> dict[str, Any]:
    return {
        "id": identifier,
        "title": "Surface Reflectance",
        "description": "optical vegetation red nir",
        "sci:doi": doi,
        "extent": {
            "spatial": {"bbox": [[-180, -90, 180, 90]]},
            "temporal": {"interval": [[None, None]]},
        },
        "summaries": {
            "gsd": [10],
            "eo:bands": [{"common_name": "red"}, {"common_name": "nir"}],
        },
    }


def test_federation_groups_exact_duplicates_and_keeps_typed_provider_failures(
    scout_request: ScoutRequest,
) -> None:
    scout = FederatedScout(
        {
            "alpha": Adapter("https://a.test/stac", [_collection("a", "10.1234/shared")]),
            "beta": Adapter("https://b.test/stac", [_collection("b", "10.1234/shared")]),
            "limited": ProviderFailureAdapter("https://limited.test/stac", []),
        }
    )

    result = scout.discover(scout_request)

    assert len(result.candidates) == 2
    assert len(result.duplicate_groups) == 1
    assert result.duplicate_groups[0].safe_to_collapse is True
    assert {candidate.provider_key for candidate in result.duplicate_groups[0].candidates} == {
        "alpha",
        "beta",
    }
    assert len(result.failures) == 1
    assert result.failures[0].provider_key == "limited"
    assert result.failures[0].error_type == "ProviderRateLimitError"
    assert result.failures[0].status_code == 429
    assert result.failures[0].retryable is True


def test_federation_does_not_mask_programming_errors(
    scout_request: ScoutRequest,
) -> None:
    scout = FederatedScout(
        {
            "good": Adapter("https://good.test/stac", [_collection("good", "10.1/good")]),
            "buggy": ProgrammingBugAdapter("https://buggy.test/stac", []),
        }
    )

    with pytest.raises(RuntimeError, match="internal invariant failed"):
        scout.discover(scout_request)


def test_federation_marks_provider_deadline_as_typed_timeout(
    scout_request: ScoutRequest,
) -> None:
    release = Event()
    scout = FederatedScout(
        {
            "fast": Adapter("https://fast.test/stac", [_collection("fast", "10.1/fast")]),
            "slow": SlowAdapter("https://slow.test/stac", release),
        }
    )

    try:
        result = scout.discover(
            scout_request,
            overall_timeout_s=0.01,
            max_workers=2,
        )
    finally:
        release.set()

    assert [candidate.provider_key for candidate in result.candidates] == ["fast"]
    assert len(result.failures) == 1
    assert result.failures[0].provider_key == "slow"
    assert result.failures[0].error_type == "ProviderTimeoutError"
    assert result.failures[0].retryable is True


def test_federation_respects_global_limit(scout_request: ScoutRequest) -> None:
    scout = FederatedScout(
        {
            "alpha": Adapter(
                "https://a.test/stac",
                [_collection("one", "10.1/one"), _collection("two", "10.1/two")],
            )
        }
    )

    result = scout.discover(scout_request, per_provider_limit=2, limit=1)

    assert len(result.candidates) == 1


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"per_provider_limit": 0}, "per_provider_limit"),
        ({"limit": -1}, "limit"),
        ({"max_workers": 0}, "max_workers"),
        ({"overall_timeout_s": 0}, "overall_timeout_s"),
        ({"overall_timeout_s": inf}, "overall_timeout_s"),
        ({"overall_timeout_s": nan}, "overall_timeout_s"),
    ],
)
def test_federation_rejects_invalid_execution_limits(
    scout_request: ScoutRequest,
    kwargs: dict[str, Any],
    message: str,
) -> None:
    scout = FederatedScout(
        {"alpha": Adapter("https://a.test/stac", [_collection("one", "10.1/one")])}
    )

    with pytest.raises(ValueError, match=message):
        scout.discover(scout_request, **kwargs)


def test_provider_network_error_is_a_provider_failure(
    scout_request: ScoutRequest,
) -> None:
    class NetworkAdapter(Adapter):
        def list_collections(self) -> list[dict[str, Any]]:
            raise ProviderNetworkError(
                "upstream unavailable",
                status_code=503,
                retryable=True,
            )

    result = FederatedScout(
        {"network": NetworkAdapter("https://network.test/stac", [])}
    ).discover(scout_request)

    assert result.candidates == ()
    assert result.failures[0].error_type == "ProviderNetworkError"
    assert result.failures[0].status_code == 503
    assert result.failures[0].retryable is True


def test_from_registry_applies_one_network_policy_to_all_adapters() -> None:
    policy = ProviderNetworkPolicy(
        connect_timeout_s=1.5,
        read_timeout_s=4.0,
        max_retries=1,
    )

    scout = FederatedScout.from_registry(
        ProviderRegistry.builtin(),
        ["earth-search", "planetary-computer"],
        network_policy=policy,
    )

    assert set(scout.adapters) == {"earth-search", "planetary-computer"}
    assert all(
        getattr(adapter, "network_policy", None) is policy
        for adapter in scout.adapters.values()
    )
