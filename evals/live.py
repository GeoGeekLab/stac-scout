from __future__ import annotations

import json
from datetime import UTC, datetime

from stac_scout.federation import FederatedScout
from stac_scout.health import check_providers
from stac_scout.models import DataType, ScoutRequest, TimeRange
from stac_scout.registry import ProviderRegistry


def main() -> int:
    registry = ProviderRegistry.builtin()
    providers = registry.all()
    health = check_providers(providers, timeout=15.0)

    request = ScoutRequest(
        task="optical surface reflectance for vegetation analysis",
        place="Singapore",
        datetime=TimeRange(
            start=datetime(2024, 6, 1, tzinfo=UTC),
            end=datetime(2024, 6, 30, tzinfo=UTC),
        ),
        data_type=DataType.OPTICAL,
        required_measurements=("red", "nir"),
        max_spatial_resolution_m=30,
    )
    discovery = FederatedScout.from_registry(registry).discover(
        request,
        per_provider_limit=5,
        limit=10,
    )

    report = {
        "health": [item.model_dump(mode="json") for item in health],
        "candidate_count": len(discovery.candidates),
        "candidates": [
            {
                "provider": candidate.provider_key,
                "collection_id": candidate.dataset.collection_id,
                "score": candidate.score,
            }
            for candidate in discovery.candidates
        ],
        "duplicate_group_count": len(discovery.duplicate_groups),
        "failures": [
            {
                "provider": failure.provider_key,
                "error_type": failure.error_type,
                "message": failure.message,
            }
            for failure in discovery.failures
        ],
    }
    print(json.dumps(report, indent=2, default=str))
    return 0 if discovery.candidates else 1


if __name__ == "__main__":
    raise SystemExit(main())
