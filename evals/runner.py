from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from stac_scout.identity import dataset_identity
from stac_scout.models import DataType, GeoTask, IdentityStrength, ScoutRequest, TemporalStrategy
from stac_scout.normalize import normalize_collection
from stac_scout.tasking import TaskAdvisor


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


class TaskExpectations(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_type: DataType
    required_measurements: tuple[str, ...]
    temporal_strategy: TemporalStrategy
    follow_up_requirements: tuple[str, ...] = ()


class TaskCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    task_type: GeoTask
    request: ScoutRequest
    expectations: TaskExpectations


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


def load_task_cases(root: Path) -> list[TaskCase]:
    return [
        TaskCase.model_validate_json(path.read_text(encoding="utf-8"))
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


def validate_task_cases(cases: list[TaskCase]) -> None:
    advisor = TaskAdvisor()
    for case in cases:
        advice = advisor.advise(case.request, case.task_type)
        expected = case.expectations
        if advice.enriched_request.data_type is not expected.data_type:
            raise SystemExit(f"{case.name}: unexpected derived data type")
        if not set(expected.required_measurements).issubset(
            advice.enriched_request.required_measurements
        ):
            raise SystemExit(f"{case.name}: missing derived measurements")
        if advice.profile.temporal_strategy is not expected.temporal_strategy:
            raise SystemExit(f"{case.name}: unexpected temporal strategy")
        if advice.follow_up_requirements != expected.follow_up_requirements:
            raise SystemExit(f"{case.name}: unexpected follow-up requirements")


def main() -> int:
    root = Path(__file__).parent
    request_cases = load_cases(root / "cases")
    federation_cases = load_federation_cases(root / "federation_cases")
    task_cases = load_task_cases(root / "task_cases")
    if not request_cases:
        raise SystemExit("no request evaluation cases found")

    validate_request_cases(request_cases)
    validate_federation_cases(federation_cases)
    validate_task_cases(task_cases)
    total = len(request_cases) + len(federation_cases) + len(task_cases)
    print(f"validated {total} evaluation cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
