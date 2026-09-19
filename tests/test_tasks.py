from __future__ import annotations

import pytest

from stac_scout.models import DataType, GeoTask, TemporalStrategy
from stac_scout.tasks import TaskRegistry, UnknownTaskError


def test_builtin_task_registry_contains_expected_archetypes() -> None:
    registry = TaskRegistry.builtin()

    profiles = registry.all()

    assert len(profiles) == 8
    assert [profile.task_type for profile in profiles] == sorted(
        GeoTask,
        key=lambda task_type: task_type.value,
    )


def test_wildfire_profile_encodes_nbr_requirements() -> None:
    profile = TaskRegistry.builtin().get(GeoTask.WILDFIRE_IMPACT)

    assert profile.data_type is DataType.OPTICAL
    assert profile.temporal_strategy is TemporalStrategy.BEFORE_AFTER
    assert profile.required_measurements == ("nir", "swir22")
    assert profile.sources


def test_flood_profile_keeps_polarization_preferred() -> None:
    profile = TaskRegistry.builtin().get(GeoTask.FLOOD_EXTENT)

    assert profile.data_type is DataType.SAR
    assert profile.required_measurements == ()
    assert profile.preferred_measurements == ("vv", "vh")


def test_registry_rejects_unknown_task() -> None:
    with pytest.raises(UnknownTaskError):
        TaskRegistry.builtin().get("missing")


def test_registry_requires_tasks_table() -> None:
    with pytest.raises(ValueError, match="tasks table"):
        TaskRegistry.from_mapping({})


def test_registry_rejects_duplicate_rule_ids() -> None:
    raw = {
        "tasks": {
            "vegetation_condition": {
                "label": "Vegetation",
                "rule_id": "duplicate",
                "data_type": "optical",
                "temporal_strategy": "single_window",
                "rationale": "one",
            },
            "snow_cover": {
                "label": "Snow",
                "rule_id": "duplicate",
                "data_type": "optical",
                "temporal_strategy": "single_window",
                "rationale": "two",
            },
        }
    }

    with pytest.raises(ValueError, match="duplicate task rule_id"):
        TaskRegistry.from_mapping(raw)
