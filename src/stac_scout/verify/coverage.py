from __future__ import annotations

from typing import Any

from pyproj import Geod
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

_GEOD = Geod(ellps="WGS84")


def geodesic_area(geometry: BaseGeometry) -> float:
    if geometry.is_empty:
        return 0.0
    area, _ = _GEOD.geometry_area_perimeter(geometry)
    return abs(float(area))


def coverage_metrics(
    aoi_geojson: dict[str, Any],
    item_geojson: dict[str, Any],
) -> tuple[float, float]:
    aoi = shape(aoi_geojson)
    item = shape(item_geojson)
    if not aoi.is_valid or not item.is_valid:
        raise ValueError("coverage geometries must be valid")

    intersection = aoi.intersection(item)
    intersection_area = geodesic_area(intersection)
    aoi_area = geodesic_area(aoi)
    item_area = geodesic_area(item)

    coverage = min(1.0, intersection_area / aoi_area) if aoi_area else 0.0
    item_fraction = min(1.0, intersection_area / item_area) if item_area else 0.0
    return coverage, item_fraction
