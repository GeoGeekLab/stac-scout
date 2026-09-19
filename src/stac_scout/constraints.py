from __future__ import annotations

from stac_scout.models import (
    ConstraintCheck,
    ConstraintStatus,
    DatasetCard,
    ScoutRequest,
)


def evaluate_constraints(card: DatasetCard, request: ScoutRequest) -> tuple[ConstraintCheck, ...]:
    checks: list[ConstraintCheck] = []

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

    return tuple(checks)
