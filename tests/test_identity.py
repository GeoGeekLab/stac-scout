from __future__ import annotations

from stac_scout.identity import dataset_identity
from stac_scout.models import DatasetCard, IdentityStrength


def test_doi_identity_is_exact_and_normalized() -> None:
    card = DatasetCard(
        catalog_url="https://a.test/stac",
        collection_id="dataset-a",
        doi="https://doi.org/10.1234/EXAMPLE",
    )

    identity = dataset_identity(card)

    assert identity.key == "doi:10.1234/example"
    assert identity.strength is IdentityStrength.EXACT


def test_semantic_identity_is_probable_across_catalogs() -> None:
    first = DatasetCard(
        catalog_url="https://a.test/stac",
        collection_id="sentinel-2-l2a",
        platforms=("sentinel-2a", "sentinel-2b"),
        instruments=("msi",),
    )
    second = first.model_copy(update={"catalog_url": "https://b.test/stac"})

    first_identity = dataset_identity(first)
    second_identity = dataset_identity(second)

    assert first_identity == second_identity
    assert first_identity.strength is IdentityStrength.PROBABLE


def test_local_identity_keeps_catalogs_distinct() -> None:
    first = DatasetCard(catalog_url="https://a.test/stac", collection_id="local")
    second = DatasetCard(catalog_url="https://b.test/stac", collection_id="local")

    assert dataset_identity(first).key != dataset_identity(second).key
    assert dataset_identity(first).strength is IdentityStrength.LOCAL
