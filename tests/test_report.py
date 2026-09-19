from __future__ import annotations

from datetime import UTC, datetime

from stac_scout.models import (
    AccessPlan,
    CandidateAssessment,
    DecisionReport,
    Evidence,
    ScoutRequest,
    TimeRange,
    VerificationStatus,
)


def test_decision_report_serializes_evidence() -> None:
    observed_at = datetime(2026, 9, 19, tzinfo=UTC)
    request = ScoutRequest(
        task="vegetation analysis",
        place="Singapore",
        datetime=TimeRange(
            start=datetime(2026, 6, 1, tzinfo=UTC),
            end=datetime(2026, 6, 30, tzinfo=UTC),
        ),
    )
    candidate = CandidateAssessment(
        catalog_url="https://example.test/stac",
        collection_id="sentinel-2-l2a",
        status=VerificationStatus.VERIFIED_AVAILABLE,
        evidence=(
            Evidence(
                source="item-search",
                claim="matching items",
                value=14,
                observed_at=observed_at,
            ),
        ),
    )
    report = DecisionReport(
        request=request,
        recommendation=candidate,
        access_plan=AccessPlan(strategy="windowed-cog", assets=("red", "nir")),
        generated_at=observed_at,
    )

    payload = report.model_dump(mode="json")

    assert payload["recommendation"]["status"] == "verified_available"
    assert payload["access_plan"]["strategy"] == "windowed-cog"
