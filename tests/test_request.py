from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from stac_scout.models import AccessPolicy, DataType, ScoutRequest, TimeRange


def test_time_range_rejects_reverse_order() -> None:
    with pytest.raises(ValidationError, match="end must not be earlier than start"):
        TimeRange(
            start=datetime(2026, 6, 2, tzinfo=UTC),
            end=datetime(2026, 6, 1, tzinfo=UTC),
        )


def test_time_range_requires_timezone_aware_values() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        TimeRange(
            start=datetime(2026, 6, 1),
            end=datetime(2026, 6, 2),
        )


def test_time_range_normalizes_to_utc() -> None:
    local = timezone(timedelta(hours=8))
    time_range = TimeRange(
        start=datetime(2026, 6, 1, 8, tzinfo=local),
        end=datetime(2026, 6, 2, 8, tzinfo=local),
    )

    assert time_range.start == datetime(2026, 6, 1, tzinfo=UTC)
    assert time_range.end == datetime(2026, 6, 2, tzinfo=UTC)
    assert time_range.start.tzinfo is UTC
    assert time_range.end.tzinfo is UTC


def test_request_requires_location() -> None:
    with pytest.raises(ValidationError, match="either geometry or place"):
        ScoutRequest(
            task="vegetation analysis",
            datetime=TimeRange(
                start=datetime(2026, 6, 1, tzinfo=UTC),
                end=datetime(2026, 6, 30, tzinfo=UTC),
            ),
        )


def test_request_rejects_non_area_geometry() -> None:
    with pytest.raises(ValidationError, match="Polygon or MultiPolygon"):
        ScoutRequest(
            task="vegetation analysis",
            geometry={"type": "Point", "coordinates": [103.8, 1.3]},
            datetime=TimeRange(
                start=datetime(2026, 6, 1, tzinfo=UTC),
                end=datetime(2026, 6, 30, tzinfo=UTC),
            ),
        )


def test_request_rejects_invalid_polygon() -> None:
    with pytest.raises(ValidationError, match="topologically valid"):
        ScoutRequest(
            task="vegetation analysis",
            geometry={
                "type": "Polygon",
                "coordinates": [
                    [[103.8, 1.2], [104.0, 1.4], [104.0, 1.2], [103.8, 1.4], [103.8, 1.2]]
                ],
            },
            datetime=TimeRange(
                start=datetime(2026, 6, 1, tzinfo=UTC),
                end=datetime(2026, 6, 30, tzinfo=UTC),
            ),
        )


def test_request_rejects_coordinates_outside_wgs84_bounds() -> None:
    with pytest.raises(ValidationError, match="WGS84"):
        ScoutRequest(
            task="vegetation analysis",
            geometry={
                "type": "Polygon",
                "coordinates": [
                    [[181.0, 1.2], [181.2, 1.2], [181.2, 1.4], [181.0, 1.4], [181.0, 1.2]]
                ],
            },
            datetime=TimeRange(
                start=datetime(2026, 6, 1, tzinfo=UTC),
                end=datetime(2026, 6, 30, tzinfo=UTC),
            ),
        )


def test_request_normalizes_measurement_names() -> None:
    request = ScoutRequest(
        task="vegetation analysis",
        place="Singapore",
        datetime=TimeRange(
            start=datetime(2026, 6, 1, tzinfo=UTC),
            end=datetime(2026, 6, 30, tzinfo=UTC),
        ),
        required_measurements=(" red ", "NIR", "nir"),
    )

    assert request.required_measurements == ("red", "NIR")


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
