from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from stac_scout.models import AccessPolicy, DataType, ScoutRequest, TimeRange


def test_time_range_rejects_reverse_order() -> None:
    with pytest.raises(ValidationError, match="end must not be earlier than start"):
        TimeRange(
            start=datetime(2026, 6, 2, tzinfo=UTC),
            end=datetime(2026, 6, 1, tzinfo=UTC),
        )


def test_request_requires_location() -> None:
    with pytest.raises(ValidationError, match="either geometry or place"):
        ScoutRequest(
            task="vegetation analysis",
            datetime=TimeRange(
                start=datetime(2026, 6, 1, tzinfo=UTC),
                end=datetime(2026, 6, 30, tzinfo=UTC),
            ),
        )


def test_request_round_trip() -> None:
    request = ScoutRequest(
        task="vegetation analysis",
        place="Singapore",
        datetime=TimeRange(
            start=datetime(2026, 6, 1, tzinfo=UTC),
            end=datetime(2026, 6, 30, tzinfo=UTC),
        ),
        data_type=DataType.OPTICAL,
        required_measurements=("red", "nir"),
        max_spatial_resolution_m=10,
        max_cloud_cover=20,
        access=AccessPolicy.OPEN,
    )

    restored = ScoutRequest.model_validate_json(request.model_dump_json())

    assert restored == request
