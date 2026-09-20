from __future__ import annotations

from stac_scout.constraints import (
    evaluate_constraints,
    evaluate_item_constraints,
    evaluate_plan_constraints,
    has_failed_constraint,
    summarize_item_constraints,
)
from stac_scout.models import (
    AccessPolicy,
    AssetChoice,
    AssetInfo,
    BandInfo,
    ConstraintStatus,
    DatasetCard,
    DataType,
    ScoutRequest,
)


def _optical_assets(*, gsd: float = 10) -> tuple[AssetInfo, ...]:
    return (
        AssetInfo(
            key="B04",
            gsd_m=gsd,
            bands=(BandInfo(common_name="red"),),
        ),
        AssetInfo(
            key="B08",
            gsd_m=gsd,
            bands=(BandInfo(common_name="nir"),),
        ),
    )


def test_constraints_pass_known_measurements(scout_request: ScoutRequest) -> None:
    card = DatasetCard(
        catalog_url="https://example.test/stac",
        collection_id="good",
        spatial_resolution_m=10,
        assets=_optical_assets(),
    )

    checks = evaluate_constraints(card, scout_request)

    assert [check.status for check in checks] == [ConstraintStatus.PASS, ConstraintStatus.PASS]


def test_constraints_preserve_unknown_metadata(scout_request: ScoutRequest) -> None:
    card = DatasetCard(
        catalog_url="https://example.test/stac",
        collection_id="unknown",
    )

    checks = evaluate_constraints(card, scout_request)

    assert all(check.status is ConstraintStatus.UNKNOWN for check in checks)


def test_constraints_fail_known_mismatch(scout_request: ScoutRequest) -> None:
    card = DatasetCard(
        catalog_url="https://example.test/stac",
        collection_id="bad",
        spatial_resolution_m=30,
        assets=(
            AssetInfo(
                key="B04",
                gsd_m=30,
                bands=(BandInfo(common_name="red"),),
            ),
        ),
    )

    checks = evaluate_constraints(card, scout_request)

    assert [check.status for check in checks] == [ConstraintStatus.FAIL, ConstraintStatus.FAIL]
    assert has_failed_constraint(checks)


def test_constraints_enforce_declared_data_type(scout_request: ScoutRequest) -> None:
    request = scout_request.model_copy(update={"data_type": DataType.SAR})
    sar = DatasetCard(
        catalog_url="https://example.test/stac",
        collection_id="sar",
        data_type=DataType.SAR,
        spatial_resolution_m=10,
        assets=_optical_assets(),
    )
    optical = sar.model_copy(update={"collection_id": "optical", "data_type": DataType.OPTICAL})

    assert evaluate_constraints(sar, request)[0].status is ConstraintStatus.PASS
    assert evaluate_constraints(optical, request)[0].status is ConstraintStatus.FAIL


def test_source_resolution_uses_requested_measurement_not_collection_minimum(
    scout_request: ScoutRequest,
) -> None:
    request = scout_request.model_copy(
        update={
            "required_measurements": ("swir16",),
            "max_source_resolution_m": 20,
        }
    )
    card = DatasetCard(
        catalog_url="https://example.test/stac",
        collection_id="mixed-resolution",
        spatial_resolution_m=10,
        assets=(
            AssetInfo(
                key="B02",
                gsd_m=10,
                bands=(BandInfo(common_name="blue"),),
            ),
            AssetInfo(
                key="B11",
                gsd_m=60,
                bands=(BandInfo(common_name="swir16"),),
            ),
        ),
    )

    checks = evaluate_constraints(card, request)
    by_name = {check.name: check for check in checks}

    assert by_name["measurements"].status is ConstraintStatus.PASS
    assert by_name["source_resolution_m"].status is ConstraintStatus.FAIL
    assert by_name["source_resolution_m"].observed == {"swir16": (60.0,)}


def test_source_resolution_is_unknown_without_measurement_specific_gsd(
    scout_request: ScoutRequest,
) -> None:
    card = DatasetCard(
        catalog_url="https://example.test/stac",
        collection_id="unknown-gsd",
        spatial_resolution_m=10,
        assets=(
            AssetInfo(key="B04", bands=(BandInfo(common_name="red"),)),
            AssetInfo(key="B08", bands=(BandInfo(common_name="nir"),)),
        ),
    )

    checks = evaluate_constraints(card, scout_request)
    by_name = {check.name: check for check in checks}

    assert by_name["measurements"].status is ConstraintStatus.PASS
    assert by_name["source_resolution_m"].status is ConstraintStatus.UNKNOWN


def test_constraints_report_downstream_checks_as_unknown(
    scout_request: ScoutRequest,
) -> None:
    request = scout_request.model_copy(
        update={
            "max_cloud_cover": 20,
            "access": AccessPolicy.OPEN,
            "max_data_volume_bytes": 1000,
        }
    )
    card = DatasetCard(
        catalog_url="https://example.test/stac",
        collection_id="known",
        spatial_resolution_m=10,
        assets=_optical_assets(),
    )

    checks = evaluate_constraints(card, request)
    by_name = {check.name: check for check in checks}

    assert by_name["cloud_cover"].status is ConstraintStatus.UNKNOWN
    assert by_name["access"].status is ConstraintStatus.UNKNOWN
    assert by_name["data_volume_bytes"].status is ConstraintStatus.UNKNOWN


def test_item_cloud_constraint_pass_fail_unknown(scout_request: ScoutRequest) -> None:
    request = scout_request.model_copy(update={"max_cloud_cover": 20})
    passing = evaluate_item_constraints(
        {"properties": {"eo:cloud_cover": 10}},
        request,
    )
    failing = evaluate_item_constraints(
        {"properties": {"eo:cloud_cover": 40}},
        request,
    )
    unknown = evaluate_item_constraints(
        {"properties": {}},
        request,
    )

    assert passing[0].status is ConstraintStatus.PASS
    assert failing[0].status is ConstraintStatus.FAIL
    assert unknown[0].status is ConstraintStatus.UNKNOWN


def test_item_constraint_summary_prefers_proven_pass(scout_request: ScoutRequest) -> None:
    request = scout_request.model_copy(update={"max_cloud_cover": 20})
    checks = [
        evaluate_item_constraints({"properties": {"eo:cloud_cover": 40}}, request),
        evaluate_item_constraints({"properties": {}}, request),
        evaluate_item_constraints({"properties": {"eo:cloud_cover": 10}}, request),
    ]

    summary = summarize_item_constraints(checks, request)

    assert summary[0].status is ConstraintStatus.PASS
    assert summary[0].observed == {
        "passing_items": 1,
        "failing_items": 1,
        "unknown_items": 1,
    }


def test_plan_volume_constraint_pass_fail_unknown(scout_request: ScoutRequest) -> None:
    request = scout_request.model_copy(
        update={
            "required_measurements": (),
            "max_source_resolution_m": None,
            "max_data_volume_bytes": 1000,
        }
    )

    assert evaluate_plan_constraints(900, request)[0].status is ConstraintStatus.PASS
    assert evaluate_plan_constraints(1100, request)[0].status is ConstraintStatus.FAIL
    assert evaluate_plan_constraints(None, request)[0].status is ConstraintStatus.UNKNOWN


def test_collection_resolution_fallback_without_required_measurements(
    scout_request: ScoutRequest,
) -> None:
    request = scout_request.model_copy(update={"required_measurements": ()})
    unknown = DatasetCard(
        catalog_url="https://example.test/stac",
        collection_id="unknown",
    )
    passing = unknown.model_copy(update={"collection_id": "passing", "spatial_resolution_m": 5})
    failing = unknown.model_copy(update={"collection_id": "failing", "spatial_resolution_m": 30})

    assert evaluate_constraints(unknown, request)[0].status is ConstraintStatus.UNKNOWN
    assert evaluate_constraints(passing, request)[0].status is ConstraintStatus.PASS
    assert evaluate_constraints(failing, request)[0].status is ConstraintStatus.FAIL


def test_item_constraint_summary_covers_fail_and_empty(
    scout_request: ScoutRequest,
) -> None:
    request = scout_request.model_copy(update={"max_cloud_cover": 20})
    failing_checks = [
        evaluate_item_constraints({"properties": {"eo:cloud_cover": 80}}, request)
    ]

    failing = summarize_item_constraints(failing_checks, request)
    empty = summarize_item_constraints([], request)

    assert failing[0].status is ConstraintStatus.FAIL
    assert empty[0].status is ConstraintStatus.UNKNOWN
    assert "no Items" in (empty[0].reason or "")


def test_plan_constraints_reject_incomplete_item_asset_coverage(
    scout_request: ScoutRequest,
) -> None:
    choice = AssetChoice(
        measurement="red",
        asset_key="B04",
        match_basis="common_name",
        selection_reason="fixture",
        gsd_m=10,
        gsd_complete=True,
        item_coverage_complete=False,
        resampling="bilinear",
        resampling_basis="fixture",
    )
    request = scout_request.model_copy(update={"required_measurements": ("red",)})

    checks = evaluate_plan_constraints(100, request, asset_choices=(choice,))
    by_name = {check.name: check for check in checks}

    assert by_name["asset_selection"].status is ConstraintStatus.FAIL
    assert "not present on every" in (by_name["asset_selection"].reason or "")


def test_plan_constraints_preserve_defensive_unknown_asset_selection(
    scout_request: ScoutRequest,
) -> None:
    request = scout_request.model_copy(
        update={
            "required_measurements": ("red", "nir"),
            "max_source_resolution_m": None,
        }
    )
    choice = AssetChoice(
        measurement="red",
        asset_key="B04",
        match_basis="common_name",
        selection_reason="fixture",
        item_coverage_complete=True,
    )

    checks = evaluate_plan_constraints(100, request, asset_choices=(choice,))

    assert checks[0].name == "asset_selection"
    assert checks[0].status is ConstraintStatus.UNKNOWN


def test_plan_constraints_preserve_unknown_selected_asset_gsd(
    scout_request: ScoutRequest,
) -> None:
    request = scout_request.model_copy(update={"required_measurements": ("red",)})
    choice = AssetChoice(
        measurement="red",
        asset_key="B04",
        match_basis="common_name",
        selection_reason="fixture",
        gsd_m=None,
        gsd_complete=False,
        item_coverage_complete=True,
    )

    checks = evaluate_plan_constraints(100, request, asset_choices=(choice,))
    by_name = {check.name: check for check in checks}

    assert by_name["asset_selection"].status is ConstraintStatus.PASS
    assert by_name["source_resolution_m"].status is ConstraintStatus.UNKNOWN
    assert "not fully declared" in (by_name["source_resolution_m"].reason or "")
