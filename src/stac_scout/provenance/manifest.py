from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from stac_scout import __version__
from stac_scout.models import AccessPlan, AvailabilityProbe, Manifest, ScoutRequest


def build_manifest(
    request: ScoutRequest,
    *,
    catalog_url: str,
    collection_id: str,
    probe: AvailabilityProbe,
    access_plan: AccessPlan,
    generated_at: datetime | None = None,
) -> Manifest:
    query = {
        "collections": [collection_id],
        "intersects": request.geometry,
        "datetime": f"{request.datetime.start.isoformat()}/{request.datetime.end.isoformat()}",
    }
    warnings = list(probe.warnings)
    warnings.extend(access_plan.notes)
    return Manifest(
        scout_version=__version__,
        generated_at=generated_at or datetime.now(UTC),
        request=request,
        catalog_url=catalog_url,
        collection_id=collection_id,
        query=query,
        item_ids=tuple(item.item_id for item in probe.items),
        asset_keys=access_plan.assets,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def write_manifest(manifest: Manifest, path: Path) -> None:
    path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")


def read_manifest(path: Path) -> Manifest:
    return Manifest.model_validate_json(path.read_text(encoding="utf-8"))
