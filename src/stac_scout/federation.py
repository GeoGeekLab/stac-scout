from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from stac_scout.catalogs import CatalogAdapter, build_adapter
from stac_scout.identity import dataset_identity
from stac_scout.models import (
    ConstraintCheck,
    DatasetCard,
    DatasetIdentity,
    IdentityStrength,
    ScoutRequest,
)
from stac_scout.registry import ProviderRegistry
from stac_scout.scout import ScoutEngine


@dataclass(frozen=True, slots=True)
class FederatedCandidate:
    provider_key: str
    dataset: DatasetCard
    score: float
    constraints: tuple[ConstraintCheck, ...]
    identity: DatasetIdentity


@dataclass(frozen=True, slots=True)
class DuplicateGroup:
    identity: DatasetIdentity
    candidates: tuple[FederatedCandidate, ...]

    @property
    def safe_to_collapse(self) -> bool:
        return self.identity.strength is IdentityStrength.EXACT


@dataclass(frozen=True, slots=True)
class ProviderFailure:
    provider_key: str
    error_type: str
    message: str


@dataclass(frozen=True, slots=True)
class FederatedDiscovery:
    candidates: tuple[FederatedCandidate, ...]
    duplicate_groups: tuple[DuplicateGroup, ...]
    failures: tuple[ProviderFailure, ...]


class FederatedScout:
    def __init__(self, adapters: Mapping[str, CatalogAdapter]) -> None:
        self.adapters = dict(adapters)

    @classmethod
    def from_registry(
        cls,
        registry: ProviderRegistry,
        provider_keys: Sequence[str] | None = None,
    ) -> FederatedScout:
        providers = registry.select(provider_keys)
        return cls({provider.key: build_adapter(provider) for provider in providers})

    def discover(
        self,
        request: ScoutRequest,
        *,
        per_provider_limit: int = 10,
        limit: int | None = 20,
    ) -> FederatedDiscovery:
        candidates: list[FederatedCandidate] = []
        failures: list[ProviderFailure] = []

        for provider_key, adapter in sorted(self.adapters.items()):
            try:
                results = ScoutEngine(adapter).discover(request, limit=per_provider_limit)
            except Exception as exc:
                failures.append(
                    ProviderFailure(
                        provider_key=provider_key,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                )
                continue

            for result in results:
                candidates.append(
                    FederatedCandidate(
                        provider_key=provider_key,
                        dataset=result.dataset,
                        score=result.score,
                        constraints=result.constraints,
                        identity=dataset_identity(result.dataset),
                    )
                )

        candidates.sort(
            key=lambda candidate: (
                -candidate.score,
                candidate.provider_key,
                candidate.dataset.collection_id,
            )
        )
        duplicate_groups = _duplicate_groups(candidates)
        visible = candidates if limit is None else candidates[:limit]
        return FederatedDiscovery(
            candidates=tuple(visible),
            duplicate_groups=duplicate_groups,
            failures=tuple(failures),
        )


def _duplicate_groups(candidates: Sequence[FederatedCandidate]) -> tuple[DuplicateGroup, ...]:
    grouped: dict[str, list[FederatedCandidate]] = defaultdict(list)
    for candidate in candidates:
        if candidate.identity.strength is not IdentityStrength.LOCAL:
            grouped[candidate.identity.key].append(candidate)

    groups = [
        DuplicateGroup(identity=members[0].identity, candidates=tuple(members))
        for members in grouped.values()
        if len(members) > 1
    ]
    groups.sort(key=lambda group: group.identity.key)
    return tuple(groups)
