from __future__ import annotations

import pytest

from stac_scout.verify import coverage_metrics


def test_coverage_metrics_full_overlap(aoi: dict[str, object]) -> None:
    coverage, item_fraction = coverage_metrics(aoi, aoi)

    assert coverage == pytest.approx(1.0)
    assert item_fraction == pytest.approx(1.0)


def test_coverage_metrics_partial_overlap(aoi: dict[str, object]) -> None:
    item = {
        "type": "Polygon",
        "coordinates": [[[103.9, 1.2], [104.1, 1.2], [104.1, 1.4], [103.9, 1.4], [103.9, 1.2]]],
    }

    coverage, item_fraction = coverage_metrics(aoi, item)

    assert coverage == pytest.approx(0.5, rel=0.02)
    assert item_fraction == pytest.approx(0.5, rel=0.02)


def test_coverage_rejects_invalid_geometry(aoi: dict[str, object]) -> None:
    invalid = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]],
    }

    with pytest.raises(ValueError, match="valid"):
        coverage_metrics(aoi, invalid)
