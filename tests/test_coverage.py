from __future__ import annotations

import pytest
from shapely.geometry import Polygon

from stac_scout.verify import coverage_metrics, geodesic_area


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


def test_coverage_handles_unsplit_antimeridian_polygon() -> None:
    aoi = {
        "type": "Polygon",
        "coordinates": [[[179, -1], [-179, -1], [-179, 1], [179, 1], [179, -1]]],
    }
    item = {
        "type": "Polygon",
        "coordinates": [[[179.5, -1], [-179.5, -1], [-179.5, 1], [179.5, 1], [179.5, -1]]],
    }

    coverage, item_fraction = coverage_metrics(aoi, item)

    assert coverage == pytest.approx(0.5, rel=0.01)
    assert item_fraction == pytest.approx(1.0, rel=0.01)


def test_coverage_handles_antimeridian_multipolygon() -> None:
    aoi = {
        "type": "MultiPolygon",
        "coordinates": [
            [[[179, -1], [180, -1], [180, 1], [179, 1], [179, -1]]],
            [[[-180, -1], [-179, -1], [-179, 1], [-180, 1], [-180, -1]]],
        ],
    }

    coverage, item_fraction = coverage_metrics(aoi, aoi)

    assert coverage == pytest.approx(1.0)
    assert item_fraction == pytest.approx(1.0)


def test_coverage_handles_high_latitude_aoi() -> None:
    aoi = {
        "type": "Polygon",
        "coordinates": [[[-30, 82], [30, 82], [30, 88], [-30, 88], [-30, 82]]],
    }
    eastern_half = {
        "type": "Polygon",
        "coordinates": [[[0, 82], [30, 82], [30, 88], [0, 88], [0, 82]]],
    }

    coverage, item_fraction = coverage_metrics(aoi, eastern_half)

    assert coverage == pytest.approx(0.5, rel=0.01)
    assert item_fraction == pytest.approx(1.0, rel=0.01)


def test_coverage_respects_polygon_holes() -> None:
    aoi = {
        "type": "Polygon",
        "coordinates": [
            [[-2, -2], [2, -2], [2, 2], [-2, 2], [-2, -2]],
            [[-1, -1], [-1, 1], [1, 1], [1, -1], [-1, -1]],
        ],
    }
    item_inside_hole = {
        "type": "Polygon",
        "coordinates": [
            [[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5], [-0.5, -0.5]]
        ],
    }

    assert coverage_metrics(aoi, item_inside_hole) == (0.0, 0.0)


def test_coverage_handles_large_aoi_without_geodesic_half_globe_assumption() -> None:
    aoi = {
        "type": "Polygon",
        "coordinates": [[[-80, -60], [80, -60], [80, 60], [-80, 60], [-80, -60]]],
    }

    coverage, item_fraction = coverage_metrics(aoi, aoi)

    assert coverage == pytest.approx(1.0)
    assert item_fraction == pytest.approx(1.0)


def test_coverage_does_not_create_antipodal_false_overlap() -> None:
    aoi = {
        "type": "Polygon",
        "coordinates": [[[-1, -1], [1, -1], [1, 1], [-1, 1], [-1, -1]]],
    }
    opposite_item = {
        "type": "Polygon",
        "coordinates": [[[178, -1], [180, -1], [180, 1], [178, 1], [178, -1]]],
    }

    assert coverage_metrics(aoi, opposite_item) == (0.0, 0.0)


@pytest.mark.parametrize(
    "invalid",
    [
        {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]],
        },
        {"type": "Polygon", "coordinates": []},
        {"type": "Point", "coordinates": [0, 0]},
        {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
    ],
)
def test_coverage_rejects_invalid_or_non_areal_geometry(
    aoi: dict[str, object],
    invalid: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match=r"geometry|Polygon|area"):
        coverage_metrics(aoi, invalid)


def test_geodesic_area_orients_holes_before_measurement() -> None:
    polygon = Polygon(
        [(-2, -2), (2, -2), (2, 2), (-2, 2), (-2, -2)],
        holes=[[(-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1)]],
    )
    outer = Polygon([(-2, -2), (2, -2), (2, 2), (-2, 2), (-2, -2)])

    assert 0 < geodesic_area(polygon) < geodesic_area(outer)
