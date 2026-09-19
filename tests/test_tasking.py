from __future__ import annotations

from stac_scout.models import DataType, GeoTask, RequirementStrength, ScoutRequest
from stac_scout.tasking import TaskAdvisor


def test_advisor_derives_required_data_needs(scout_request: ScoutRequest) -> None:
    request = scout_request.model_copy(
        update={
            "data_type": DataType.ANY,
            "required_measurements": (),
            "preferences": {},
        }
    )

    advice = TaskAdvisor().advise(request, GeoTask.WILDFIRE_IMPACT)

    assert advice.enriched_request.data_type is DataType.OPTICAL
    assert advice.enriched_request.required_measurements == ("nir", "swir22")
    assert advice.follow_up_requirements == ("comparison_windows",)
    required = [
        item for item in advice.derivations if item.strength is RequirementStrength.REQUIRED
    ]
    assert {item.field for item in required} == {"data_type", "required_measurements"}


def test_advisor_preserves_incompatible_explicit_data_type(
    scout_request: ScoutRequest,
) -> None:
    request = scout_request.model_copy(
        update={
            "data_type": DataType.SAR,
            "required_measurements": (),
            "preferences": {},
        }
    )

    advice = TaskAdvisor().advise(request, GeoTask.VEGETATION_CONDITION)

    assert advice.enriched_request.data_type is DataType.SAR
    assert advice.enriched_request.required_measurements == ()
    assert "modality-specific defaults were skipped" in advice.notes[0]
    assert "task_preferred_measurements" not in advice.enriched_request.preferences


def test_advisor_preserves_explicit_task_preferences(scout_request: ScoutRequest) -> None:
    request = scout_request.model_copy(
        update={"preferences": {"task_temporal_strategy": "time_series"}}
    )

    advice = TaskAdvisor().advise(request, GeoTask.VEGETATION_CONDITION)

    assert advice.enriched_request.preferences["task_temporal_strategy"] == "time_series"
    assert advice.follow_up_requirements == ()
    assert any("task_temporal_strategy" in note for note in advice.notes)


def test_advisor_keeps_user_measurements_and_adds_missing_requirements(
    scout_request: ScoutRequest,
) -> None:
    request = scout_request.model_copy(update={"required_measurements": ("thermal", "nir")})

    advice = TaskAdvisor().advise(request, GeoTask.WILDFIRE_IMPACT)

    assert advice.enriched_request.required_measurements == ("thermal", "nir", "swir22")


def test_single_window_task_has_no_temporal_follow_up(scout_request: ScoutRequest) -> None:
    advice = TaskAdvisor().advise(scout_request, GeoTask.VEGETATION_CONDITION)

    assert advice.follow_up_requirements == ()
