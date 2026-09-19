from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from stac_scout.models import ScoutRequest


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


def load_cases(root: Path) -> list[EvaluationCase]:
    cases: list[EvaluationCase] = []
    for path in sorted(root.glob("*.json")):
        cases.append(EvaluationCase.model_validate_json(path.read_text(encoding="utf-8")))
    return cases


def main() -> int:
    root = Path(__file__).parent / "cases"
    cases = load_cases(root)
    if not cases:
        raise SystemExit("no evaluation cases found")

    for case in cases:
        expected = set(case.expectations.required_measurements)
        actual = set(case.request.required_measurements)
        if not expected.issubset(actual):
            raise SystemExit(f"{case.name}: request is missing expected measurements")

    print(f"validated {len(cases)} evaluation cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
