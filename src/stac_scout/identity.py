from __future__ import annotations

import hashlib
import json
import re

from stac_scout.models import DatasetCard, DatasetIdentity, IdentityStrength

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _slug(value: str) -> str:
    return _NON_ALNUM.sub("-", value.casefold()).strip("-")


def _normalized_doi(value: str) -> str:
    doi = value.strip().casefold()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix) :]
            break
    return doi


def _valid_normalized_doi(value: str) -> bool:
    return re.fullmatch(r"10\.\d{4,9}/\S+", value) is not None


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:20]


def dataset_identity(card: DatasetCard) -> DatasetIdentity:
    if card.doi:
        doi = _normalized_doi(card.doi)
        if _valid_normalized_doi(doi):
            return DatasetIdentity(
                key=f"doi:{doi}",
                strength=IdentityStrength.EXACT,
                basis=("sci:doi",),
            )

    semantic = {
        "collection_id": _slug(card.collection_id),
        "platforms": sorted(_slug(value) for value in card.platforms),
        "constellations": sorted(_slug(value) for value in card.constellations),
        "instruments": sorted(_slug(value) for value in card.instruments),
    }
    has_semantic_evidence = any(
        semantic[key] for key in ("platforms", "constellations", "instruments")
    )
    if has_semantic_evidence:
        basis = tuple(
            key
            for key in ("collection_id", "platforms", "constellations", "instruments")
            if semantic[key]
        )
        return DatasetIdentity(
            key=f"semantic:{_fingerprint(semantic)}",
            strength=IdentityStrength.PROBABLE,
            basis=basis,
        )

    local = {"catalog_url": card.catalog_url, "collection_id": card.collection_id}
    return DatasetIdentity(
        key=f"local:{_fingerprint(local)}",
        strength=IdentityStrength.LOCAL,
        basis=("catalog_url", "collection_id"),
    )
