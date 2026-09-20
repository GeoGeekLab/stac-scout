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
    BandInfo,
    ConstraintStatus,
    DataType,
    DatasetCard,
    ScoutRequest,
)


def test_constraints_pass_known_measurements(scout_request: ScoutRequest) -> None:
    card = DatasetCard(
        catalog_url="https://example.test/stac",
        collection_id="good",
        spatial_resolution_m=10,
        bands=(BandInfo(common_name="red"), BandInfo(common_name="nir")),
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
        bands=(BandInfo(common_name="red"),),
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
        bands=(BandInfo(common_name="red"), BandInfo(common_name="nir")),
    )
    optical = sar.model_copy(
        update={"collection_id": "optical", "data_type": DataType.OPTICAL}
    )

    assert evaluate_constraints(sar, request)[0].status is ConstraintStatus.PASS
    assert evaluate_constraints(optical, request)[0].status is ConstraintStatus.FAIL


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
        bands=(BandInfo(common_name="red"), BandInfo(common_name="nir")),
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
    request = scout_request.model_copy(update={"max_data_volume_bytes": 1000})

    assert evaluate_plan_constraints(900, request)[0].status is ConstraintStatus.PASS
    assert evaluate_plan_constraints(1100, request)[0].status is ConstraintStatus.FAIL
    assert evaluate_plan_constraints(None, request)[0].status is ConstraintStatus.UNKNOWN
