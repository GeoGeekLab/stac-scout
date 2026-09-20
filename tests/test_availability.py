from __future__ import annotations

from stac_scout.models import VerificationStatus
from stac_scout.verify import probe_items


def test_probe_items_reports_verified_empty(aoi: dict[str, object]) -> None:
    probe = probe_items([], aoi)

    assert probe.status is VerificationStatus.VERIFIED_EMPTY
    assert probe.items_checked == 0


def test_probe_items_collects_item_evidence(aoi: dict[str, object]) -> None:
    items = [
        {
            "id": "scene-1",
            "geometry": aoi,
            "properties": {"datetime": "2026-06-10T02:00:00Z", "eo:cloud_cover": 7.5},
            "assets": {"B04": {}, "B08": {}},
        }
    ]

    probe = probe_items(items, aoi)

    assert probe.status is VerificationStatus.VERIFIED_AVAILABLE
    assert probe.max_coverage_ratio == 1.0
    assert probe.items[0].cloud_cover == 7.5
    assert probe.items[0].asset_keys == ("B04", "B08")


def test_probe_items_tolerates_invalid_metadata(aoi: dict[str, object]) -> None:
    items = [
        {
            "id": "broken",
            "geometry": {"type": "Polygon", "coordinates": []},
            "properties": {"datetime": "not-a-date", "eo:cloud_cover": "unknown"},
            "assets": [],
        }
    ]

    probe = probe_items(items, aoi)

    assert probe.items[0].datetime is None
    assert probe.items[0].cloud_cover is None
    assert probe.items[0].asset_keys == ()


def test_probe_items_degrades_non_object_properties_to_warning(
    aoi: dict[str, object],
) -> None:
    items = [
        {
            "id": "broken-properties",
            "geometry": aoi,
            "properties": [],
            "assets": {},
        }
    ]

    probe = probe_items(items, aoi)

    assert probe.status is VerificationStatus.VERIFIED_AVAILABLE
    assert probe.items[0].datetime is None
    assert probe.items[0].cloud_cover is None
    assert any("non-object properties" in warning for warning in probe.warnings)
