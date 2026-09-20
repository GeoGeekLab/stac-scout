from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from stac_scout.models import AssetChoice
_MATCH_RANK = {
    "band_name": 1,
    "common_name": 2,
    "asset_key": 3,
}


def _all_band_definitions(asset: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    bands: list[dict[str, Any]] = []
    for key in ("bands", "eo:bands", "raster:bands"):
        value = asset.get(key)
        if isinstance(value, list):
            bands.extend(entry for entry in value if isinstance(entry, dict))
    return tuple(bands)


@dataclass(slots=True)
class _Candidate:
    key: str
    match_rank: int = 0
    match_basis: str = ""
    roles: set[str] = field(default_factory=set)
    media_types: set[str] = field(default_factory=set)
    gsds: list[float] = field(default_factory=list)
    occurrences: int = 0
    gsd_observations: int = 0

    @property
    def max_gsd_m(self) -> float | None:
        return max(self.gsds, default=None)

    @property
    def gsd_complete(self) -> bool:
        return self.occurrences > 0 and self.gsd_observations == self.occurrences


def _measurement_match(
    key: str,
    asset: dict[str, Any],
    target: str,
) -> tuple[int, str] | None:
    best: tuple[int, str] | None = None
    if key.casefold() == target:
        best = (_MATCH_RANK["asset_key"], "asset_key")

    for band in _all_band_definitions(asset):
        common_name = band.get("common_name")
        if isinstance(common_name, str) and common_name.casefold() == target:
            candidate = (_MATCH_RANK["common_name"], "common_name")
            if best is None or candidate[0] > best[0]:
                best = candidate

        name = band.get("name")
        if isinstance(name, str) and name.casefold() == target:
            candidate = (_MATCH_RANK["band_name"], "band_name")
            if best is None or candidate[0] > best[0]:
                best = candidate

    return best


def _positive_number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return float(value)
    return None


def _asset_gsd(asset: dict[str, Any], item: dict[str, Any]) -> float | None:
    asset_gsd = _positive_number(asset.get("gsd"))
    if asset_gsd is not None:
        return asset_gsd

    properties = item.get("properties")
    if isinstance(properties, dict):
        return _positive_number(properties.get("gsd"))
    return None


def _role_rank(roles: set[str]) -> int:
    if "data" in roles:
        return 3
    if not roles:
        return 2
    if roles & {"visual", "overview"}:
        return 1
    return 0


def _media_rank(media_types: set[str]) -> int:
    for media_type in media_types:
        value = media_type.casefold()
        if value.startswith("image/") or "geotiff" in value or "cog" in value:
            return 1
    return 0


def _source_fit_rank(candidate: _Candidate, limit_m: float | None) -> int:
    if limit_m is None:
        return 1

    gsd = candidate.max_gsd_m
    if gsd is None:
        return 1
    if gsd > limit_m:
        return 0
    if candidate.gsd_complete:
        return 2
    return 1


def _candidate_score(
    candidate: _Candidate,
    *,
    item_count: int,
    max_source_resolution_m: float | None,
) -> tuple[int, int, int, int, int, float]:
    gsd = candidate.max_gsd_m
    return (
        _source_fit_rank(candidate, max_source_resolution_m),
        int(item_count > 0 and candidate.occurrences == item_count),
        _role_rank(candidate.roles),
        candidate.match_rank,
        _media_rank(candidate.media_types),
        -gsd if gsd is not None else float("-inf"),
    )


def _selection_reason(
    candidate: _Candidate,
    *,
    item_count: int,
    max_source_resolution_m: float | None,
) -> str:
    parts = [f"{candidate.match_basis} match"]
    if "data" in candidate.roles:
        parts.append("data role")
    if candidate.occurrences == item_count and item_count:
        parts.append("present on all inspected Items")
    else:
        parts.append(f"present on {candidate.occurrences}/{item_count} inspected Items")

    gsd = candidate.max_gsd_m
    if gsd is not None:
        completeness = "complete" if candidate.gsd_complete else "partial"
        parts.append(f"{completeness} GSD evidence up to {gsd:g} m")
        if max_source_resolution_m is not None:
            relation = (
                "within"
                if candidate.gsd_complete and gsd <= max_source_resolution_m
                else "not proven within"
            )
            parts.append(f"{relation} {max_source_resolution_m:g} m source limit")
    else:
        parts.append("GSD unknown")

    return "; ".join(parts)


def select_asset_choices(
    items: list[dict[str, Any]],
    measurements: tuple[str, ...],
    *,
    max_source_resolution_m: float | None = None,
) -> tuple[tuple[AssetChoice, ...], tuple[str, ...], tuple[str, ...]]:
    if not measurements:
        return ((), (), ())

    choices: list[AssetChoice] = []
    missing: list[str] = []
    ambiguous: list[str] = []
    item_count = len(items)

    for measurement in measurements:
        target = measurement.casefold()
        candidates: dict[str, _Candidate] = {}

        for item in items:
            assets = item.get("assets", {})
            if not isinstance(assets, dict):
                continue

            for key, asset in assets.items():
                if not isinstance(key, str) or not isinstance(asset, dict):
                    continue
                match = _measurement_match(key, asset, target)
                if match is None:
                    continue

                candidate = candidates.setdefault(key, _Candidate(key=key))
                candidate.occurrences += 1
                if match[0] > candidate.match_rank:
                    candidate.match_rank, candidate.match_basis = match

                roles = asset.get("roles")
                if isinstance(roles, list):
                    candidate.roles.update(
                        str(role).casefold() for role in roles if isinstance(role, str)
                    )

                media_type = asset.get("type")
                if isinstance(media_type, str):
                    candidate.media_types.add(media_type)

                gsd = _asset_gsd(asset, item)
                if gsd is not None:
                    candidate.gsds.append(gsd)
                    candidate.gsd_observations += 1

        if not candidates:
            missing.append(measurement)
            continue

        scored = [
            (
                _candidate_score(
                    candidate,
                    item_count=item_count,
                    max_source_resolution_m=max_source_resolution_m,
                ),
                candidate,
            )
            for candidate in candidates.values()
        ]
        best_score = max(score for score, _ in scored)
        winners = [candidate for score, candidate in scored if score == best_score]
        if len(winners) != 1:
            ambiguous.append(measurement)
            continue

        winner = winners[0]
        choices.append(
            AssetChoice(
                measurement=measurement,
                asset_key=winner.key,
                match_basis=winner.match_basis,
                selection_reason=_selection_reason(
                    winner,
                    item_count=item_count,
                    max_source_resolution_m=max_source_resolution_m,
                ),
                gsd_m=winner.max_gsd_m,
                gsd_complete=winner.gsd_complete,
                item_coverage_complete=item_count > 0 and winner.occurrences == item_count,
            )
        )

    return (tuple(choices), tuple(missing), tuple(ambiguous))


def select_asset_keys(
    items: list[dict[str, Any]],
    measurements: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    choices, missing, ambiguous = select_asset_choices(items, measurements)
    keys = tuple(dict.fromkeys(choice.asset_key for choice in choices))
    unresolved = tuple(dict.fromkeys((*missing, *ambiguous)))
    return (keys, unresolved)
