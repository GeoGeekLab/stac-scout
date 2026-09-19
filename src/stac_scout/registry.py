from __future__ import annotations

import tomllib
from collections.abc import Iterable, Mapping
from importlib.resources import files
from typing import Any

from stac_scout.models import ProviderSpec


class UnknownProviderError(KeyError):
    pass


class ProviderRegistry:
    def __init__(self, providers: Mapping[str, ProviderSpec]) -> None:
        self._providers = dict(providers)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> ProviderRegistry:
        provider_data = raw.get("providers")
        if not isinstance(provider_data, dict):
            raise ValueError("provider registry must contain a providers table")

        providers: dict[str, ProviderSpec] = {}
        for key, value in provider_data.items():
            if not isinstance(key, str) or not isinstance(value, dict):
                raise ValueError("provider entries must be named tables")
            providers[key] = ProviderSpec.model_validate({"key": key, **value})
        return cls(providers)

    @classmethod
    def builtin(cls) -> ProviderRegistry:
        resource = files("stac_scout").joinpath("data/providers.toml")
        with resource.open("rb") as stream:
            return cls.from_mapping(tomllib.load(stream))

    def get(self, key: str) -> ProviderSpec:
        try:
            return self._providers[key]
        except KeyError as exc:
            raise UnknownProviderError(key) from exc

    def all(self, *, include_disabled: bool = False) -> tuple[ProviderSpec, ...]:
        providers = [
            provider
            for provider in self._providers.values()
            if include_disabled or provider.enabled
        ]
        return tuple(sorted(providers, key=lambda provider: provider.key))

    def select(self, keys: Iterable[str] | None = None) -> tuple[ProviderSpec, ...]:
        if keys is None:
            return self.all()

        selected: list[ProviderSpec] = []
        seen: set[str] = set()
        for key in keys:
            if key in seen:
                continue
            provider = self.get(key)
            if not provider.enabled:
                raise ValueError(f"provider is disabled: {key}")
            selected.append(provider)
            seen.add(key)
        return tuple(selected)
