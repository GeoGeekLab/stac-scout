from __future__ import annotations

from datetime import UTC, datetime

import pytest

from stac_scout.models import ScoutRequest, TimeRange


@pytest.fixture
def aoi() -> dict[str, object]:
    return {
        "type": "Polygon",
        "coordinates": [[[103.8, 1.2], [104.0, 1.2], [104.0, 1.4], [103.8, 1.4], [103.8, 1.2]]],
    }


@pytest.fixture
def scout_request(aoi: dict[str, object]) -> ScoutRequest:
    return ScoutRequest(
        task="vegetation analysis",
        geometry=aoi,
        datetime=TimeRange(
            start=datetime(2026, 6, 1, tzinfo=UTC),
            end=datetime(2026, 6, 30, tzinfo=UTC),
        ),
        required_measurements=("red", "nir"),
        max_spatial_resolution_m=10,
    )
