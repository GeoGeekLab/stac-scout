from __future__ import annotations

from stac_scout.constraints import evaluate_constraints
from stac_scout.models import BandInfo, ConstraintStatus, DatasetCard, ScoutRequest


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
