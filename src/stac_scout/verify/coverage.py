from __future__ import annotations

from math import isfinite
from typing import Any, Iterable

from pyproj import CRS, Geod, Transformer
from shapely import segmentize
from shapely.errors import GEOSException
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient
from shapely.ops import transform

_GEOD = Geod(ellps="WGS84")
_CRS84 = CRS.from_user_input("OGC:CRS84")
_MAX_SEGMENT_DEGREES = 1.0


def _oriented_areal_geometry(geometry: BaseGeometry) -> BaseGeometry:
    if isinstance(geometry, Polygon):
        return orient(geometry, sign=1.0)
    if isinstance(geometry, MultiPolygon):
        return MultiPolygon([orient(polygon, sign=1.0) for polygon in geometry.geoms])
    raise ValueError("geometry must be a Polygon or MultiPolygon")


def geodesic_area(geometry: BaseGeometry) -> float:
    """Return WGS84 geodesic area for an areal Shapely geometry.

    pyproj documents a half-globe limitation for geometry_area_perimeter. Coverage
    ratios therefore use a local equal-area projection instead of this helper.
    """

    if geometry.is_empty:
        return 0.0
    oriented = _oriented_areal_geometry(geometry)
    area, _ = _GEOD.geometry_area_perimeter(oriented)
    return abs(float(area))


def _areal_geometry(raw: dict[str, Any], *, label: str) -> Polygon | MultiPolygon:
    try:
        geometry = shape(raw)
    except (GEOSException, KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{label} geometry is not valid GeoJSON") from exc

    if not isinstance(geometry, (Polygon, MultiPolygon)):
        raise ValueError(f"{label} geometry must be a Polygon or MultiPolygon")
    if geometry.is_empty:
        raise ValueError(f"{label} geometry must not be empty")
    if not geometry.is_valid:
        raise ValueError(f"{label} geometry must be topologically valid")
    if geometry.area <= 0:
        raise ValueError(f"{label} geometry must have non-zero area")
    return geometry


def _exterior_positions(geometry: Polygon | MultiPolygon) -> Iterable[tuple[float, float]]:
    polygons = (geometry,) if isinstance(geometry, Polygon) else geometry.geoms
    for polygon in polygons:
        coordinates = list(polygon.exterior.coords)
        if len(coordinates) > 1 and coordinates[0][:2] == coordinates[-1][:2]:
            coordinates = coordinates[:-1]
        for coordinate in coordinates:
            yield float(coordinate[0]), float(coordinate[1])


def _longitude_center(longitudes: Iterable[float]) -> float:
    values = sorted({longitude % 360.0 for longitude in longitudes})
    if not values:
        raise ValueError("AOI geometry has no exterior coordinates")
    if len(values) == 1:
        center = values[0]
    else:
        largest_gap_index = max(
            range(len(values)),
            key=lambda index: (
                values[(index + 1) % len(values)]
                + (360.0 if index == len(values) - 1 else 0.0)
                - values[index]
            ),
        )
        arc_start = values[(largest_gap_index + 1) % len(values)]
        arc_end = values[largest_gap_index]
        if arc_end < arc_start:
            arc_end += 360.0
        center = (arc_start + arc_end) / 2.0

    normalized = ((center + 180.0) % 360.0) - 180.0
    if abs(normalized + 180.0) < 1e-12:
        return 180.0
    if abs(normalized) < 1e-12:
        return 0.0
    return normalized


def _ring_coordinates(
    coordinates: Iterable[tuple[float, ...]],
    *,
    center_longitude: float,
) -> list[tuple[float, float]]:
    raw = list(coordinates)
    if not raw:
        return []

    first_longitude = float(raw[0][0])
    first = first_longitude + 360.0 * round(
        (center_longitude - first_longitude) / 360.0
    )
    unwrapped = [(first, float(raw[0][1]))]
    previous = first

    for coordinate in raw[1:]:
        longitude = float(coordinate[0])
        raw_delta = longitude - previous
        delta = ((raw_delta + 180.0) % 360.0) - 180.0
        if abs(delta + 180.0) < 1e-12 and raw_delta > 0:
            delta = 180.0
        current = previous + delta
        unwrapped.append((current, float(coordinate[1])))
        previous = current

    if len(raw) > 1 and raw[0][:2] == raw[-1][:2]:
        unwrapped[-1] = unwrapped[0]
    return unwrapped


def _unwrap_longitudes(
    geometry: Polygon | MultiPolygon,
    *,
    center_longitude: float,
) -> Polygon | MultiPolygon:
    def unwrap_polygon(polygon: Polygon) -> Polygon:
        return Polygon(
            _ring_coordinates(
                polygon.exterior.coords,
                center_longitude=center_longitude,
            ),
            [
                _ring_coordinates(ring.coords, center_longitude=center_longitude)
                for ring in polygon.interiors
            ],
        )

    if isinstance(geometry, Polygon):
        result: Polygon | MultiPolygon = unwrap_polygon(geometry)
    else:
        result = MultiPolygon([unwrap_polygon(polygon) for polygon in geometry.geoms])

    if result.is_empty or not result.is_valid:
        raise ValueError("coverage geometry became invalid after longitude normalization")
    return result


def _projection(
    aoi: Polygon | MultiPolygon,
    *,
    center_longitude: float,
) -> Transformer:
    positions = list(_exterior_positions(aoi))
    latitudes = [latitude for _, latitude in positions]
    center_latitude = (min(latitudes) + max(latitudes)) / 2.0

    target = CRS.from_proj4(
        "+proj=laea "
        f"+lat_0={center_latitude:.12f} "
        f"+lon_0={center_longitude:.12f} "
        "+ellps=WGS84 +units=m +no_defs"
    )
    return Transformer.from_crs(
        _CRS84,
        target,
        always_xy=True,
        force_over=True,
    )


def _projected_area(geometry: BaseGeometry, transformer: Transformer) -> float:
    densified = segmentize(geometry, max_segment_length=_MAX_SEGMENT_DEGREES)
    projected = transform(transformer.transform, densified)
    if projected.is_empty:
        return 0.0
    if not projected.is_valid:
        raise ValueError("coverage geometry became invalid after projection")
    if not all(isfinite(value) for value in projected.bounds):
        raise ValueError("coverage projection produced non-finite coordinates")
    return float(projected.area)


def coverage_metrics(
    aoi_geojson: dict[str, Any],
    item_geojson: dict[str, Any],
) -> tuple[float, float]:
    """Measure AOI coverage and Item read fraction with dateline-safe topology."""

    aoi = _areal_geometry(aoi_geojson, label="AOI")
    item = _areal_geometry(item_geojson, label="Item")

    center_longitude = _longitude_center(
        longitude for longitude, _ in _exterior_positions(aoi)
    )
    normalized_aoi = _unwrap_longitudes(aoi, center_longitude=center_longitude)
    normalized_item = _unwrap_longitudes(item, center_longitude=center_longitude)

    intersection = normalized_aoi.intersection(normalized_item)
    if intersection.is_empty:
        return 0.0, 0.0
    if not intersection.is_valid:
        raise ValueError("coverage intersection is not topologically valid")

    transformer = _projection(aoi, center_longitude=center_longitude)
    intersection_area = _projected_area(intersection, transformer)
    aoi_area = _projected_area(normalized_aoi, transformer)
    item_area = _projected_area(normalized_item, transformer)

    if aoi_area <= 0 or item_area <= 0:
        raise ValueError("coverage geometries must have non-zero projected area")

    coverage = max(0.0, min(1.0, intersection_area / aoi_area))
    item_fraction = max(0.0, min(1.0, intersection_area / item_area))
    return coverage, item_fraction
