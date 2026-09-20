from __future__ import annotations

from stac_scout.models import (
    AvailabilityProbe,
    ConstraintStatus,
    ItemEvidence,
    ScoutRequest,
    VerificationStatus,
)
from stac_scout.planning import (
    build_access_plan,
    estimate_asset_bytes,
    resampling_for,
    select_asset_choices,
    select_asset_keys,
)


def _items(aoi: dict[str, object]) -> list[dict[str, object]]:
    return [
        {
            "id": "scene-1",
            "geometry": aoi,
            "properties": {},
            "assets": {
                "B04": {
                    "type": "image/tiff; application=geotiff",
                    "roles": ["data"],
                    "gsd": 10,
                    "eo:bands": [{"common_name": "red"}],
                    "file:size": 1000,
                },
                "B08": {
                    "type": "image/tiff; application=geotiff",
                    "roles": ["data"],
                    "gsd": 10,
                    "eo:bands": [{"common_name": "nir"}],
                    "file:size": 2000,
                },
            },
        }
    ]


def _probe(fraction: float = 1.0) -> AvailabilityProbe:
    return AvailabilityProbe(
        status=VerificationStatus.VERIFIED_AVAILABLE,
        items_checked=1,
        items=(ItemEvidence(item_id="scene-1", item_fraction_read=fraction),),
    )


def _constraint(plan: object, name: str):
    return next(check for check in plan.constraints if check.name == name)


def test_select_asset_keys_uses_band_semantics(aoi: dict[str, object]) -> None:
    selected, missing = select_asset_keys(_items(aoi), ("red", "nir"))

    assert selected == ("B04", "B08")
    assert missing == ()


def test_asset_selection_prefers_data_evidence_over_lexical_key() -> None:
    items = [
        {
            "id": "scene-1",
            "properties": {},
            "assets": {
                "A_visual": {
                    "type": "image/png",
                    "roles": ["visual"],
                    "gsd": 10,
                    "eo:bands": [{"common_name": "red"}],
                },
                "Z_data": {
                    "type": "image/tiff; application=geotiff",
                    "roles": ["data"],
                    "gsd": 10,
                    "eo:bands": [{"common_name": "red"}],
                },
            },
        }
    ]

    choices, missing, ambiguous = select_asset_choices(items, ("red",))

    assert missing == ()
    assert ambiguous == ()
    assert choices[0].asset_key == "Z_data"
    assert "data role" in choices[0].selection_reason


def test_asset_selection_refuses_unresolved_tie() -> None:
    items = [
        {
            "id": "scene-1",
            "properties": {},
            "assets": {
                "A": {
                    "type": "image/tiff",
                    "roles": ["data"],
                    "gsd": 10,
                    "eo:bands": [{"common_name": "red"}],
                },
                "B": {
                    "type": "image/tiff",
                    "roles": ["data"],
                    "gsd": 10,
                    "eo:bands": [{"common_name": "red"}],
                },
            },
        }
    ]

    choices, missing, ambiguous = select_asset_choices(items, ("red",))

    assert choices == ()
    assert missing == ()
    assert ambiguous == ("red",)


def test_asset_selection_prefers_candidate_within_source_resolution_limit() -> None:
    items = [
        {
            "id": "scene-1",
            "properties": {},
            "assets": {
                "coarse": {
                    "type": "image/tiff",
                    "roles": ["data"],
                    "gsd": 20,
                    "eo:bands": [{"common_name": "nir"}],
                },
                "fine": {
                    "type": "image/tiff",
                    "roles": ["data"],
                    "gsd": 10,
                    "eo:bands": [{"common_name": "nir"}],
                },
            },
        }
    ]

    choices, _, ambiguous = select_asset_choices(
        items,
        ("nir",),
        max_source_resolution_m=15,
    )

    assert ambiguous == ()
    assert choices[0].asset_key == "fine"
    assert choices[0].gsd_m == 10


def test_estimate_asset_bytes_uses_item_fraction(aoi: dict[str, object]) -> None:
    estimate = estimate_asset_bytes(_items(aoi), ("B04", "B08"), probe=_probe(0.25))

    assert estimate == 750


def test_build_access_plan(scout_request: ScoutRequest, aoi: dict[str, object]) -> None:
    plan, missing = build_access_plan(scout_request, _items(aoi), _probe(0.5))

    assert missing == ()
    assert plan.assets == ("B04", "B08")
    assert plan.estimated_bytes == 1500
    assert plan.output_resolution is None
    assert plan.resampling == {"red": "bilinear", "nir": "bilinear"}
    assert _constraint(plan, "asset_selection").status is ConstraintStatus.PASS
    assert _constraint(plan, "source_resolution_m").status is ConstraintStatus.PASS


def test_build_access_plan_separates_source_and_target_resolution(
    scout_request: ScoutRequest,
    aoi: dict[str, object],
) -> None:
    request = scout_request.model_copy(
        update={
            "max_source_resolution_m": 30,
            "target_resolution_m": 20,
        }
    )

    plan, _ = build_access_plan(request, _items(aoi), _probe())

    assert plan.output_resolution == 20
    assert _constraint(plan, "source_resolution_m").status is ConstraintStatus.PASS


def test_build_access_plan_evaluates_volume_budget(
    scout_request: ScoutRequest,
    aoi: dict[str, object],
) -> None:
    request = scout_request.model_copy(update={"max_data_volume_bytes": 1000})

    plan, _ = build_access_plan(request, _items(aoi), _probe(0.5))

    assert plan.estimated_bytes == 1500
    assert _constraint(plan, "data_volume_bytes").status is ConstraintStatus.FAIL


def test_build_access_plan_preserves_unknown_volume_budget(
    scout_request: ScoutRequest,
) -> None:
    request = scout_request.model_copy(update={"max_data_volume_bytes": 1000})
    items = [
        {
            "id": "scene-1",
            "assets": {
                "B04": {
                    "roles": ["data"],
                    "gsd": 10,
                    "eo:bands": [{"common_name": "red"}],
                },
                "B08": {
                    "roles": ["data"],
                    "gsd": 10,
                    "eo:bands": [{"common_name": "nir"}],
                },
            },
        }
    ]

    plan, _ = build_access_plan(request, items, _probe())

    assert plan.estimated_bytes is None
    assert _constraint(plan, "data_volume_bytes").status is ConstraintStatus.UNKNOWN


def test_plan_reports_unresolved_measurement(
    scout_request: ScoutRequest,
) -> None:
    items = [
        {
            "id": "scene-1",
            "assets": {
                "B04": {
                    "roles": ["data"],
                    "gsd": 10,
                    "eo:bands": [{"common_name": "red"}],
                }
            },
        }
    ]

    plan, missing = build_access_plan(scout_request, items, _probe())

    assert missing == ("nir",)
    assert _constraint(plan, "asset_selection").status is ConstraintStatus.FAIL
    assert "no matching asset: nir" in plan.notes[0]
    assert any(note.startswith("asset sizes are not declared") for note in plan.notes)


def test_resampling_known_categorical_names_are_nearest() -> None:
    for measurement in ("SCL", "QA60", "Fmask", "pixel_qa"):
        assert resampling_for(measurement) == "nearest"


def test_resampling_unknown_name_is_not_invented() -> None:
    assert resampling_for("mystery_band") is None


def test_build_access_plan_uses_classification_metadata_for_resampling() -> None:
    items = [
        {
            "id": "scene-1",
            "assets": {
                "classes": {
                    "type": "image/tiff",
                    "roles": ["data"],
                    "raster:bands": [
                        {
                            "name": "class_code",
                            "classification:classes": [
                                {"value": 0, "name": "water"},
                                {"value": 1, "name": "land"},
                            ],
                        }
                    ],
                }
            },
        }
    ]
    request = ScoutRequest.model_validate(
        {
            "task": "classification",
            "place": "Singapore",
            "datetime": {
                "start": "2026-06-01T00:00:00Z",
                "end": "2026-06-02T00:00:00Z",
            },
            "required_measurements": ["class_code"],
        }
    )

    plan, missing = build_access_plan(request, items, _probe())

    assert missing == ()
    assert plan.resampling == {"class_code": "nearest"}
    assert plan.asset_choices[0].resampling_basis == (
        "selected band declares classification:classes"
    )


def test_estimate_asset_bytes_returns_none_without_sizes(aoi: dict[str, object]) -> None:
    assert estimate_asset_bytes([{"id": "x", "assets": {"red": {}}}], ("red",)) is None
