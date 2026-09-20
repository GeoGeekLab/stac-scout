from __future__ import annotations

from stac_scout.models import DataType
from stac_scout.normalize import normalize_collection


def test_normalize_collection_extracts_assets_and_resolution() -> None:
    card = normalize_collection(
        {
            "id": "sentinel-test",
            "title": "Sentinel Test",
            "description": "Surface reflectance",
            "sci:doi": "10.1234/example",
            "license": "proprietary",
            "providers": [{"name": "Example"}],
            "extent": {
                "spatial": {"bbox": [[-180, -90, 180, 90]]},
                "temporal": {"interval": [["2020-01-01T00:00:00Z", None]]},
            },
            "summaries": {
                "gsd": [20, 10],
                "platform": ["sentinel-2a", "sentinel-2b"],
                "instruments": ["msi"],
            },
            "item_assets": {
                "B04": {
                    "type": "image/tiff; application=geotiff; profile=cloud-optimized",
                    "roles": ["data"],
                    "gsd": 10,
                    "eo:bands": [{"name": "B04", "common_name": "red"}],
                }
            },
        },
        "https://example.test/stac",
    )

    assert card.spatial_resolution_m == 10
    assert card.providers == ("Example",)
    assert card.doi == "10.1234/example"
    assert card.data_type is DataType.OPTICAL
    assert card.platforms == ("sentinel-2a", "sentinel-2b")
    assert card.instruments == ("msi",)
    assert "red" in card.measurements
    assert card.assets[0].key == "B04"
    assert card.assets[0].gsd_m == 10


def test_normalize_collection_detects_sar_extension() -> None:
    card = normalize_collection(
        {
            "id": "sar-test",
            "stac_extensions": ["https://stac-extensions.github.io/sar/v1.0.0/schema.json"],
            "extent": {
                "spatial": {"bbox": [[-180, -90, 180, 90]]},
                "temporal": {"interval": [[None, None]]},
            },
            "summaries": {"sar:polarizations": ["VV", "VH"]},
        },
        "https://example.test/stac",
    )

    assert card.data_type is DataType.SAR


def test_normalize_collection_preserves_ambiguous_modality_as_unknown() -> None:
    card = normalize_collection(
        {
            "id": "ambiguous",
            "stac_extensions": [
                "https://stac-extensions.github.io/eo/v1.1.0/schema.json",
                "https://stac-extensions.github.io/sar/v1.0.0/schema.json",
            ],
            "extent": {
                "spatial": {"bbox": [[-180, -90, 180, 90]]},
                "temporal": {"interval": [[None, None]]},
            },
            "summaries": {},
        },
        "https://example.test/stac",
    )

    assert card.data_type is None


def test_normalize_collection_handles_invalid_temporal_metadata() -> None:
    card = normalize_collection(
        {
            "id": "invalid-time",
            "extent": {
                "spatial": {"bbox": [[-180, -90, 180, 90]]},
                "temporal": {"interval": [["not-a-date", None]]},
            },
            "summaries": {},
        },
        "https://example.test/stac",
    )

    assert card.temporal_start is None


def test_normalize_collection_handles_sparse_metadata() -> None:
    card = normalize_collection(
        {
            "id": "sparse",
            "extent": {"spatial": {"bbox": []}, "temporal": {"interval": []}},
            "summaries": {},
            "item_assets": {},
        },
        "https://example.test/stac",
    )

    assert card.spatial_extent is None
    assert card.temporal_start is None
    assert card.spatial_resolution_m is None
    assert card.data_type is None
    assert card.assets == ()
