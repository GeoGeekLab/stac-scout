from __future__ import annotations

from typing import Any

from stac_scout.models import (
    DataType,
    DerivedRequirement,
    GeoTask,
    RequirementStrength,
    ScoutRequest,
    TaskAdvice,
    TaskProfile,
    TemporalStrategy,
)
from stac_scout.tasks import TaskRegistry

_TASK_PREFERENCE_KEYS = {
    "temporal_strategy": "task_temporal_strategy",
    "preferred_measurements": "task_preferred_measurements",
    "preferred_processing_levels": "task_preferred_processing_levels",
    "preferred_masks": "task_preferred_masks",
}


def _derivation(
    profile: TaskProfile,
    *,
    field: str,
    value: Any,
    strength: RequirementStrength,
) -> DerivedRequirement:
    return DerivedRequirement(
        rule_id=profile.rule_id,
        field=field,
        value=value,
        strength=strength,
        rationale=profile.rationale,
    )


class TaskAdvisor:
    def __init__(self, registry: TaskRegistry | None = None) -> None:
        self.registry = registry or TaskRegistry.builtin()

    def advise(self, request: ScoutRequest, task_type: GeoTask | str) -> TaskAdvice:
        profile = self.registry.get(task_type)
        derivations: list[DerivedRequirement] = []
        notes: list[str] = []
        follow_up: list[str] = []

        compatible_modality = request.data_type in (DataType.ANY, profile.data_type)
        data_type = request.data_type
        if data_type is DataType.ANY:
            data_type = profile.data_type
            derivations.append(
                _derivation(
                    profile,
                    field="data_type",
                    value=data_type.value,
                    strength=RequirementStrength.REQUIRED,
                )
            )
        elif data_type is not profile.data_type:
            notes.append(
                "explicit data_type "
                f"{data_type.value!r} differs from task default {profile.data_type.value!r}; "
                "the explicit request was preserved and modality-specific defaults were skipped"
            )

        measurements = list(request.required_measurements)
        if compatible_modality:
            known_measurements = {value.casefold() for value in measurements}
            for measurement in profile.required_measurements:
                if measurement.casefold() in known_measurements:
                    continue
                measurements.append(measurement)
                known_measurements.add(measurement.casefold())
                derivations.append(
                    _derivation(
                        profile,
                        field="required_measurements",
                        value=measurement,
                        strength=RequirementStrength.REQUIRED,
                    )
                )

        preferences = dict(request.preferences)
        task_preferences: dict[str, Any] = {
            _TASK_PREFERENCE_KEYS["temporal_strategy"]: profile.temporal_strategy.value,
        }
        if compatible_modality:
            task_preferences.update(
                {
                    _TASK_PREFERENCE_KEYS["preferred_measurements"]: list(
                        profile.preferred_measurements
                    ),
                    _TASK_PREFERENCE_KEYS["preferred_processing_levels"]: list(
                        profile.preferred_processing_levels
                    ),
                    _TASK_PREFERENCE_KEYS["preferred_masks"]: list(profile.preferred_masks),
                }
            )

        for key, value in task_preferences.items():
            if key in preferences:
                notes.append(f"explicit preference {key!r} was preserved")
                continue
            preferences[key] = value
            derivations.append(
                _derivation(
                    profile,
                    field=f"preferences.{key}",
                    value=value,
                    strength=RequirementStrength.PREFERRED,
                )
            )

        has_explicit_temporal_strategy = (
            _TASK_PREFERENCE_KEYS["temporal_strategy"] in request.preferences
        )
        if not has_explicit_temporal_strategy:
            if (
                profile.temporal_strategy is TemporalStrategy.BEFORE_AFTER
                and "comparison_windows" not in request.preferences
            ):
                follow_up.append("comparison_windows")
            elif (
                profile.temporal_strategy is TemporalStrategy.TIME_SERIES
                and "temporal_sampling_strategy" not in request.preferences
            ):
                follow_up.append("temporal_sampling_strategy")

        enriched = request.model_copy(
            update={
                "data_type": data_type,
                "required_measurements": tuple(measurements),
                "preferences": preferences,
            }
        )
        return TaskAdvice(
            task_type=profile.task_type,
            profile=profile,
            enriched_request=enriched,
            derivations=tuple(derivations),
            follow_up_requirements=tuple(follow_up),
            notes=tuple(notes),
        )
