from __future__ import annotations

from stac_scout.normalize import normalize_collection


def test_normalize_collection_extracts_assets_and_resolution() -> None:
    card = normalize_collection(
        {
            "id": "sentinel-test",
            "title": "Sentinel Test",
            "description": "Surface reflectance",
            "license": "proprietary",
            "providers": [{"name": "Example"}],
            "extent": {
                "spatial": {"bbox": [[-180, -90, 180, 90]]},
                "temporal": {"interval": [["2020-01-01T00:00:00Z", None]]},
            },
            "summaries": {"gsd": [20, 10]},
            "item_assets": {
                "B04": {
                    "type": "image/tiff; application=geotiff; profile=cloud-optimized",
                    "roles": ["data"],
                    "eo:bands": [{"name": "B04", "common_name": "red"}],
                }
            },
        },
        "https://example.test/stac",
    )

    assert card.spatial_resolution_m == 10
    assert card.providers == ("Example",)
    assert "red" in card.measurements
    assert card.assets[0].key == "B04"


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
    assert card.assets == ()
