from __future__ import annotations

from stac_scout.models import (
    AvailabilityProbe,
    ConstraintStatus,
    ItemEvidence,
    ScoutRequest,
    VerificationStatus,
)
from stac_scout.planning import build_access_plan, estimate_asset_bytes, select_asset_keys


def _items(aoi: dict[str, object]) -> list[dict[str, object]]:
    return [
        {
            "id": "scene-1",
            "geometry": aoi,
            "properties": {},
            "assets": {
                "B04": {"eo:bands": [{"common_name": "red"}], "file:size": 1000},
                "B08": {"eo:bands": [{"common_name": "nir"}], "file:size": 2000},
            },
        }
    ]


def test_select_asset_keys_uses_band_semantics(aoi: dict[str, object]) -> None:
    selected, missing = select_asset_keys(_items(aoi), ("red", "nir"))

    assert selected == ("B04", "B08")
    assert missing == ()


def test_estimate_asset_bytes_uses_item_fraction(aoi: dict[str, object]) -> None:
    probe = AvailabilityProbe(
        status=VerificationStatus.VERIFIED_AVAILABLE,
        items_checked=1,
        items=(ItemEvidence(item_id="scene-1", item_fraction_read=0.25),),
    )

    estimate = estimate_asset_bytes(_items(aoi), ("B04", "B08"), probe=probe)

    assert estimate == 750


def test_build_access_plan(scout_request: ScoutRequest, aoi: dict[str, object]) -> None:
    probe = AvailabilityProbe(
        status=VerificationStatus.VERIFIED_AVAILABLE,
        items_checked=1,
        items=(ItemEvidence(item_id="scene-1", item_fraction_read=0.5),),
    )

    plan, missing = build_access_plan(scout_request, _items(aoi), probe)

    assert missing == ()
    assert plan.assets == ("B04", "B08")
    assert plan.estimated_bytes == 1500
    assert plan.resampling == {"red": "bilinear", "nir": "bilinear"}
    assert plan.constraints == ()


def test_build_access_plan_evaluates_volume_budget(
    scout_request: ScoutRequest,
    aoi: dict[str, object],
) -> None:
    request = scout_request.model_copy(update={"max_data_volume_bytes": 1000})
    probe = AvailabilityProbe(
        status=VerificationStatus.VERIFIED_AVAILABLE,
        items_checked=1,
        items=(ItemEvidence(item_id="scene-1", item_fraction_read=0.5),),
    )

    plan, _ = build_access_plan(request, _items(aoi), probe)

    assert plan.estimated_bytes == 1500
    assert plan.constraints[0].name == "data_volume_bytes"
    assert plan.constraints[0].status is ConstraintStatus.FAIL


def test_build_access_plan_preserves_unknown_volume_budget(
    scout_request: ScoutRequest,
) -> None:
    request = scout_request.model_copy(update={"max_data_volume_bytes": 1000})
    items = [
        {
            "id": "scene-1",
            "assets": {
                "B04": {"eo:bands": [{"common_name": "red"}]},
                "B08": {"eo:bands": [{"common_name": "nir"}]},
            },
        }
    ]
    probe = AvailabilityProbe(
        status=VerificationStatus.VERIFIED_AVAILABLE,
        items_checked=1,
        items=(ItemEvidence(item_id="scene-1"),),
    )

    plan, _ = build_access_plan(request, items, probe)

    assert plan.estimated_bytes is None
    assert plan.constraints[0].status is ConstraintStatus.UNKNOWN


def test_plan_reports_unresolved_measurement(
    aoi: dict[str, object], scout_request: ScoutRequest
) -> None:
    items = [{"id": "scene-1", "assets": {"B04": {"eo:bands": [{"common_name": "red"}]}}}]
    probe = AvailabilityProbe(
        status=VerificationStatus.VERIFIED_AVAILABLE,
        items_checked=1,
        items=(ItemEvidence(item_id="scene-1"),),
    )

    plan, missing = build_access_plan(scout_request, items, probe)

    assert missing == ("nir",)
    assert "unresolved measurements: nir" in plan.notes
    assert any(note.startswith("asset sizes are not declared") for note in plan.notes)


def test_estimate_asset_bytes_returns_none_without_sizes(aoi: dict[str, object]) -> None:
    assert estimate_asset_bytes([{"id": "x", "assets": {"red": {}}}], ("red",)) is None
