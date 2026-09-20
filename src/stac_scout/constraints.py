from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from stac_scout.models import (
    AccessPolicy,
    ConstraintCheck,
    ConstraintStatus,
    DatasetCard,
    DataType,
    ScoutRequest,
)


class ConstraintViolationError(ValueError):
    def __init__(self, message: str, checks: tuple[ConstraintCheck, ...]) -> None:
        super().__init__(message)
        self.checks = checks


def has_failed_constraint(checks: Sequence[ConstraintCheck]) -> bool:
    return any(check.status is ConstraintStatus.FAIL for check in checks)


def evaluate_constraints(card: DatasetCard, request: ScoutRequest) -> tuple[ConstraintCheck, ...]:
    """Evaluate collection-level evidence for every active hard request constraint.

    Constraints that cannot be established from Collection metadata are returned as UNKNOWN
    rather than silently omitted. Item-level and planning-level checks are refined later.
    """

    checks: list[ConstraintCheck] = []

    if request.data_type is not DataType.ANY:
        if card.data_type is None:
            status = ConstraintStatus.UNKNOWN
            reason = "collection metadata does not declare unambiguous modality evidence"
        elif card.data_type is request.data_type:
            status = ConstraintStatus.PASS
            reason = None
        else:
            status = ConstraintStatus.FAIL
            reason = "collection modality conflicts with the requested data type"
        checks.append(
            ConstraintCheck(
                name="data_type",
                status=status,
                expected=request.data_type.value,
                observed=card.data_type.value if card.data_type is not None else None,
                reason=reason,
            )
        )

    if request.required_measurements:
        available = card.measurements
        missing = tuple(
            measurement
            for measurement in request.required_measurements
            if measurement.casefold() not in available
        )
        if not available:
            status = ConstraintStatus.UNKNOWN
            reason = "collection does not declare band or asset measurement metadata"
        elif missing:
            status = ConstraintStatus.FAIL
            reason = f"missing measurements: {', '.join(missing)}"
        else:
            status = ConstraintStatus.PASS
            reason = None
        checks.append(
            ConstraintCheck(
                name="measurements",
                status=status,
                expected=request.required_measurements,
                observed=tuple(sorted(available)),
                reason=reason,
            )
        )

    if request.max_spatial_resolution_m is not None:
        if card.spatial_resolution_m is None:
            status = ConstraintStatus.UNKNOWN
            reason = "collection does not declare a spatial resolution"
        elif card.spatial_resolution_m <= request.max_spatial_resolution_m:
            status = ConstraintStatus.PASS
            reason = None
        else:
            status = ConstraintStatus.FAIL
            reason = "collection resolution exceeds the requested maximum"
        checks.append(
            ConstraintCheck(
                name="spatial_resolution_m",
                status=status,
                expected=request.max_spatial_resolution_m,
                observed=card.spatial_resolution_m,
                reason=reason,
            )
        )

    if request.max_cloud_cover is not None:
        checks.append(
            ConstraintCheck(
                name="cloud_cover",
                status=ConstraintStatus.UNKNOWN,
                expected=request.max_cloud_cover,
                observed=None,
                reason="cloud cover is an Item-level constraint and requires live Item evidence",
            )
        )

    if request.access is not AccessPolicy.ANY:
        checks.append(
            ConstraintCheck(
                name="access",
                status=ConstraintStatus.UNKNOWN,
                expected=request.access.value,
                observed=None,
                reason=(
                    "dataset asset access policy is not established by normalized Collection "
                    "metadata"
                ),
            )
        )

    if request.max_data_volume_bytes is not None:
        checks.append(
            ConstraintCheck(
                name="data_volume_bytes",
                status=ConstraintStatus.UNKNOWN,
                expected=request.max_data_volume_bytes,
                observed=None,
                reason="data volume is a planning-level constraint and requires selected assets",
            )
        )

    return tuple(checks)


def evaluate_item_constraints(
    item: dict[str, Any],
    request: ScoutRequest,
) -> tuple[ConstraintCheck, ...]:
    checks: list[ConstraintCheck] = []

    if request.max_cloud_cover is not None:
        properties = item.get("properties")
        cloud_cover = properties.get("eo:cloud_cover") if isinstance(properties, dict) else None
        if (
            not isinstance(cloud_cover, (int, float))
            or isinstance(cloud_cover, bool)
            or not 0 <= float(cloud_cover) <= 100
        ):
            status = ConstraintStatus.UNKNOWN
            observed: float | None = None
            reason = "Item does not declare a valid eo:cloud_cover value"
        else:
            observed = float(cloud_cover)
            if observed <= request.max_cloud_cover:
                status = ConstraintStatus.PASS
                reason = None
            else:
                status = ConstraintStatus.FAIL
                reason = "Item cloud cover exceeds the requested maximum"

        checks.append(
            ConstraintCheck(
                name="cloud_cover",
                status=status,
                expected=request.max_cloud_cover,
                observed=observed,
                reason=reason,
            )
        )

    return tuple(checks)


def summarize_item_constraints(
    checks_by_item: Sequence[Sequence[ConstraintCheck]],
    request: ScoutRequest,
) -> tuple[ConstraintCheck, ...]:
    summaries: list[ConstraintCheck] = []

    if request.max_cloud_cover is not None:
        cloud_checks = [
            check
            for item_checks in checks_by_item
            for check in item_checks
            if check.name == "cloud_cover"
        ]
        passing = sum(check.status is ConstraintStatus.PASS for check in cloud_checks)
        failing = sum(check.status is ConstraintStatus.FAIL for check in cloud_checks)
        unknown = sum(check.status is ConstraintStatus.UNKNOWN for check in cloud_checks)

        if passing:
            status = ConstraintStatus.PASS
            reason = None
        elif unknown:
            status = ConstraintStatus.UNKNOWN
            reason = "no inspected Item proves the cloud-cover constraint; some values are unknown"
        elif failing:
            status = ConstraintStatus.FAIL
            reason = "all inspected Items with known cloud cover exceed the requested maximum"
        else:
            status = ConstraintStatus.UNKNOWN
            reason = "no Items were available to evaluate the cloud-cover constraint"

        summaries.append(
            ConstraintCheck(
                name="cloud_cover",
                status=status,
                expected=request.max_cloud_cover,
                observed={
                    "passing_items": passing,
                    "failing_items": failing,
                    "unknown_items": unknown,
                },
                reason=reason,
            )
        )

    return tuple(summaries)


def evaluate_plan_constraints(
    estimated_bytes: int | None,
    request: ScoutRequest,
) -> tuple[ConstraintCheck, ...]:
    checks: list[ConstraintCheck] = []

    if request.max_data_volume_bytes is not None:
        if estimated_bytes is None:
            status = ConstraintStatus.UNKNOWN
            reason = "selected assets do not declare enough size metadata to estimate transfer"
        elif estimated_bytes <= request.max_data_volume_bytes:
            status = ConstraintStatus.PASS
            reason = None
        else:
            status = ConstraintStatus.FAIL
            reason = "estimated transfer exceeds the requested data-volume maximum"

        checks.append(
            ConstraintCheck(
                name="data_volume_bytes",
                status=status,
                expected=request.max_data_volume_bytes,
                observed=estimated_bytes,
                reason=reason,
            )
        )

    return tuple(checks)
