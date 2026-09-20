from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from stac_scout.identity import dataset_identity
from stac_scout.models import DataType, GeoTask, IdentityStrength, ScoutRequest, TemporalStrategy
from stac_scout.normalize import normalize_collection
from stac_scout.tasking import TaskAdvisor


REQUIRED_REGRESSION_IDS = frozenset(
    {
        "sar_request_vs_optical",
        "optical_request_vs_sar",
        "cloud_tristate",
        "required_vs_preferred_measurements",
        "doi_identity_strength",
        "multiple_collection_extents",
        "antimeridian_and_poles",
        "empty_and_over_100_items",
        "timeout_429_partial_federation",
        "categorical_resampling",
        "missing_file_size",
        "volume_budget_exceeded",
        "task_user_conflict",
        "malformed_provider_metadata",
    }
)


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


class RegressionCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    contract: str
    tests: tuple[str, ...]


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


def load_regression_cases(path: Path) -> list[RegressionCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise SystemExit("regression matrix must be a JSON array")
    return [RegressionCase.model_validate(entry) for entry in payload]


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


def _test_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }


def validate_regression_cases(cases: list[RegressionCase], repo_root: Path) -> None:
    ids = [case.id for case in cases]
    duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
    if duplicates:
        raise SystemExit(f"duplicate regression ids: {', '.join(duplicates)}")

    missing = sorted(REQUIRED_REGRESSION_IDS.difference(ids))
    if missing:
        raise SystemExit(f"missing required regression ids: {', '.join(missing)}")

    cache: dict[Path, set[str]] = {}
    for case in cases:
        if not case.tests:
            raise SystemExit(f"{case.id}: no pytest evidence declared")
        for reference in case.tests:
            relative_path, separator, function_name = reference.partition("::")
            if not separator or not function_name.startswith("test_"):
                raise SystemExit(f"{case.id}: invalid pytest node id {reference!r}")
            test_path = repo_root / relative_path
            if not test_path.is_file():
                raise SystemExit(f"{case.id}: missing test file {relative_path}")
            functions = cache.setdefault(test_path, _test_functions(test_path))
            if function_name not in functions:
                raise SystemExit(f"{case.id}: missing pytest function {reference}")


def main() -> int:
    root = Path(__file__).parent
    repo_root = root.parent
    request_cases = load_cases(root / "cases")
    federation_cases = load_federation_cases(root / "federation_cases")
    task_cases = load_task_cases(root / "task_cases")
    regression_cases = load_regression_cases(root / "regression_matrix.json")
    if not request_cases:
        raise SystemExit("no request evaluation cases found")

    validate_request_cases(request_cases)
    validate_federation_cases(federation_cases)
    validate_task_cases(task_cases)
    validate_regression_cases(regression_cases, repo_root)
    total = (
        len(request_cases)
        + len(federation_cases)
        + len(task_cases)
        + len(regression_cases)
    )
    print(f"validated {total} evaluation cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
