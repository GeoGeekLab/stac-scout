from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass

from stac_scout.catalogs import (
    CatalogAdapter,
    ProviderError,
    ProviderTimeoutError,
    build_adapter,
)
from stac_scout.identity import dataset_identity
from stac_scout.models import (
    ConstraintCheck,
    DatasetCard,
    DatasetIdentity,
    IdentityStrength,
    ScoutRequest,
)
from stac_scout.registry import ProviderRegistry
from stac_scout.scout import DiscoveryResult, ScoutEngine


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
    status_code: int | None = None
    retryable: bool = False


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

    @staticmethod
    def _provider_failure(provider_key: str, exc: ProviderError) -> ProviderFailure:
        return ProviderFailure(
            provider_key=provider_key,
            error_type=type(exc).__name__,
            message=str(exc),
            status_code=exc.status_code,
            retryable=exc.retryable,
        )

    def discover(
        self,
        request: ScoutRequest,
        *,
        per_provider_limit: int = 10,
        limit: int | None = 20,
        max_workers: int = 4,
        overall_timeout_s: float = 30.0,
    ) -> FederatedDiscovery:
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        if overall_timeout_s <= 0:
            raise ValueError("overall_timeout_s must be positive")

        candidates: list[FederatedCandidate] = []
        failures: list[ProviderFailure] = []
        if not self.adapters:
            return FederatedDiscovery(candidates=(), duplicate_groups=(), failures=())

        executor = ThreadPoolExecutor(max_workers=min(max_workers, len(self.adapters)))
        futures: dict[Future[list[DiscoveryResult]], str] = {}
        try:
            for provider_key, adapter in sorted(self.adapters.items()):
                future = executor.submit(
                    ScoutEngine(adapter).discover,
                    request,
                    limit=per_provider_limit,
                )
                futures[future] = provider_key

            done, not_done = wait(futures, timeout=overall_timeout_s)

            for future in sorted(done, key=lambda item: futures[item]):
                provider_key = futures[future]
                try:
                    results = future.result()
                except ProviderError as exc:
                    failures.append(self._provider_failure(provider_key, exc))
                    continue
                except Exception:
                    for pending in not_done:
                        pending.cancel()
                    raise

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

            for future in sorted(not_done, key=lambda item: futures[item]):
                provider_key = futures[future]
                future.cancel()
                timeout_error = ProviderTimeoutError(
                    f"provider discovery exceeded federation deadline of "
                    f"{overall_timeout_s:g} seconds",
                    retryable=True,
                )
                failures.append(self._provider_failure(provider_key, timeout_error))
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        candidates.sort(
            key=lambda candidate: (
                -candidate.score,
                candidate.provider_key,
                candidate.dataset.collection_id,
            )
        )
        failures.sort(key=lambda failure: failure.provider_key)
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
