from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from stac_scout.models import GeoTask, IntentDraft, TimeRange, UnresolvedIntentError
from stac_scout.reasoning import IntentParser, intent_instructions


class Extractor:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.schema: dict[str, Any] | None = None
        self.instructions: str | None = None

    def extract(
        self,
        text: str,
        *,
        schema: dict[str, Any],
        instructions: str,
    ) -> dict[str, Any]:
        assert text == "find optical imagery"
        self.schema = schema
        self.instructions = instructions
        return self.payload


def test_intent_draft_resolves_to_request() -> None:
    draft = IntentDraft(
        task="vegetation analysis",
        task_type=GeoTask.VEGETATION_CONDITION,
        place="Singapore",
        datetime=TimeRange(
            start=datetime(2026, 6, 1, tzinfo=UTC),
            end=datetime(2026, 6, 30, tzinfo=UTC),
        ),
        required_measurements=("red", "nir"),
    )

    request = draft.to_request()

    assert draft.task_type is GeoTask.VEGETATION_CONDITION
    assert request.place == "Singapore"
    assert request.required_measurements == ("red", "nir")


def test_intent_draft_refuses_missing_requirements() -> None:
    draft = IntentDraft(task="vegetation analysis", unresolved=("date range",))

    with pytest.raises(UnresolvedIntentError, match="date range, datetime, location"):
        draft.to_request()


def test_intent_parser_is_model_agnostic() -> None:
    extractor = Extractor(
        {
            "task": "vegetation analysis",
            "task_type": "vegetation_condition",
            "place": "Singapore",
            "unresolved": ["datetime"],
        }
    )

    draft = IntentParser(extractor).parse("find optical imagery")

    assert draft.place == "Singapore"
    assert draft.task_type is GeoTask.VEGETATION_CONDITION
    assert extractor.schema is not None
    assert "properties" in extractor.schema
    assert extractor.instructions == intent_instructions()
    assert "Do not invent coordinates" in extractor.instructions
    assert "Do not derive spectral measurements" in extractor.instructions


def test_intent_draft_migrates_legacy_resolution_and_target_grid() -> None:
    draft = IntentDraft.model_validate(
        {
            "task": "vegetation analysis",
            "place": "Singapore",
            "datetime": {
                "start": "2026-06-01T00:00:00Z",
                "end": "2026-06-30T00:00:00Z",
            },
            "max_spatial_resolution_m": 30,
            "target_crs": "EPSG:3857",
            "target_resolution_m": 20,
        }
    )

    request = draft.to_request()

    assert draft.max_source_resolution_m == 30
    assert request.max_source_resolution_m == 30
    assert request.target_crs == "EPSG:3857"
    assert request.target_resolution_m == 20


def test_intent_draft_rejects_conflicting_resolution_fields() -> None:
    with pytest.raises(ValidationError, match="use only max_source_resolution_m"):
        IntentDraft.model_validate(
            {
                "task": "vegetation analysis",
                "max_source_resolution_m": 10,
                "max_spatial_resolution_m": 30,
            }
        )
