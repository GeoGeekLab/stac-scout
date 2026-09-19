from __future__ import annotations

import tomllib
from collections.abc import Mapping
from importlib.resources import files
from typing import Any

from stac_scout.models import GeoTask, TaskProfile


class UnknownTaskError(ValueError):
    pass


class TaskRegistry:
    def __init__(self, profiles: Mapping[GeoTask, TaskProfile]) -> None:
        self._profiles = dict(profiles)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> TaskRegistry:
        task_data = raw.get("tasks")
        if not isinstance(task_data, dict):
            raise ValueError("task registry must contain a tasks table")

        profiles: dict[GeoTask, TaskProfile] = {}
        rule_ids: set[str] = set()
        for key, value in task_data.items():
            if not isinstance(key, str) or not isinstance(value, dict):
                raise ValueError("task entries must be named tables")
            task_type = GeoTask(key)
            profile = TaskProfile.model_validate({"task_type": task_type, **value})
            if profile.rule_id in rule_ids:
                raise ValueError(f"duplicate task rule_id: {profile.rule_id}")
            rule_ids.add(profile.rule_id)
            profiles[task_type] = profile
        return cls(profiles)

    @classmethod
    def builtin(cls) -> TaskRegistry:
        resource = files("stac_scout").joinpath("data/tasks.toml")
        with resource.open("rb") as stream:
            return cls.from_mapping(tomllib.load(stream))

    def get(self, task_type: GeoTask | str) -> TaskProfile:
        try:
            key = GeoTask(task_type)
        except ValueError as exc:
            raise UnknownTaskError(str(task_type)) from exc
        try:
            return self._profiles[key]
        except KeyError as exc:
            raise UnknownTaskError(str(task_type)) from exc

    def all(self) -> tuple[TaskProfile, ...]:
        return tuple(sorted(self._profiles.values(), key=lambda profile: profile.task_type.value))
