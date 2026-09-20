from __future__ import annotations

import re
from dataclasses import dataclass

from stac_scout.models import DataType, DatasetCard, ScoutRequest

_TOKEN = re.compile(r"[a-z0-9][a-z0-9._+-]*")


@dataclass(frozen=True, slots=True)
class RankedDataset:
    card: DatasetCard
    score: float


def _tokens(value: str) -> set[str]:
    return set(_TOKEN.findall(value.casefold()))


def rank_collections(
    cards: list[DatasetCard],
    request: ScoutRequest,
    *,
    limit: int = 10,
) -> list[RankedDataset]:
    query_parts = [request.task, *request.required_measurements]
    if request.data_type is not DataType.ANY:
        query_parts.append(request.data_type.value)

    query_tokens = _tokens(" ".join(query_parts))
    if not query_tokens:
        return [RankedDataset(card=card, score=0.0) for card in cards[:limit]]

    ranked: list[RankedDataset] = []
    for card in cards:
        text = " ".join(
            part for part in (card.collection_id, card.title or "", card.description or "") if part
        )
        haystack = _tokens(text) | set(card.measurements)
        if card.data_type is not None:
            haystack.add(card.data_type.value)
        overlap = len(query_tokens & haystack)
        score = overlap / len(query_tokens)
        ranked.append(RankedDataset(card=card, score=score))

    ranked.sort(key=lambda entry: (-entry.score, entry.card.collection_id))
    return ranked[:limit]
