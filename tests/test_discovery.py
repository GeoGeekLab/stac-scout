from __future__ import annotations

from stac_scout.discovery import rank_collections
from stac_scout.models import BandInfo, DatasetCard, ScoutRequest


def test_rank_collections_prefers_matching_metadata(scout_request: ScoutRequest) -> None:
    cards = [
        DatasetCard(
            catalog_url="x",
            collection_id="elevation",
            description="digital elevation model",
        ),
        DatasetCard(
            catalog_url="x",
            collection_id="surface-reflectance",
            description="optical vegetation surface reflectance",
            bands=(BandInfo(common_name="red"), BandInfo(common_name="nir")),
        ),
    ]

    ranked = rank_collections(cards, scout_request)

    assert ranked[0].card.collection_id == "surface-reflectance"
    assert ranked[0].score > ranked[1].score
