from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from stac_scout.identity import dataset_identity
from stac_scout.models import IdentityStrength, ScoutRequest
from stac_scout.normalize import normalize_collection


class Expectations(BaseModel):
    model_config = ConfigDict(extra="forbid")

    must_verify_items: bool = True
    required_measurements: tuple[str, ...] = ()
    forbidden_claims: tuple[str, ...] = ()


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    request: ScoutRequest
    expectations: Expectations


class FederationCollection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_url: str
    collection: dict[str, Any]


class FederationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    collections: tuple[FederationCollection, ...]
    expected_strength: IdentityStrength
    expected_shared_identity: bool


def load_cases(root: Path) -> list[EvaluationCase]:
    return [
        EvaluationCase.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(root.glob("*.json"))
    ]


def load_federation_cases(root: Path) -> list[FederationCase]:
    return [
        FederationCase.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(root.glob("*.json"))
    ]


def validate_request_cases(cases: list[EvaluationCase]) -> None:
    for case in cases:
        expected = set(case.expectations.required_measurements)
        actual = set(case.request.required_measurements)
        if not expected.issubset(actual):
            raise SystemExit(f"{case.name}: request is missing expected measurements")


def validate_federation_cases(cases: list[FederationCase]) -> None:
    for case in cases:
        identities = [
            dataset_identity(normalize_collection(entry.collection, entry.catalog_url))
            for entry in case.collections
        ]
        if any(identity.strength is not case.expected_strength for identity in identities):
            raise SystemExit(f"{case.name}: unexpected identity strength")
        shared = len({identity.key for identity in identities}) == 1
        if shared is not case.expected_shared_identity:
            raise SystemExit(f"{case.name}: unexpected identity grouping")


def main() -> int:
    root = Path(__file__).parent
    request_cases = load_cases(root / "cases")
    federation_cases = load_federation_cases(root / "federation_cases")
    if not request_cases:
        raise SystemExit("no request evaluation cases found")

    validate_request_cases(request_cases)
    validate_federation_cases(federation_cases)
    total = len(request_cases) + len(federation_cases)
    print(f"validated {total} evaluation cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
