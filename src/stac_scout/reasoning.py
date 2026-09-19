from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from stac_scout.models import IntentDraft


class StructuredExtractor(Protocol):
    def extract(
        self,
        text: str,
        *,
        schema: Mapping[str, Any],
        instructions: str,
    ) -> Mapping[str, Any]: ...


def intent_instructions() -> str:
    return (
        "Extract only information supported by the user's request. "
        "Do not invent coordinates, dates, dataset names, measurement names, or constraints. "
        "If the stated goal clearly maps to a task_type allowed by the schema, set task_type; "
        "otherwise leave it null and mark the ambiguity unresolved. "
        "Do not derive spectral measurements from task_type; the deterministic task registry "
        "owns that knowledge. "
        "Use unresolved for required information that is missing or ambiguous. "
        "Use assumptions only for explicit interpretation choices, never hidden guesses. "
        "Return data that conforms exactly to the supplied JSON schema."
    )


class IntentParser:
    def __init__(self, extractor: StructuredExtractor) -> None:
        self.extractor = extractor

    def parse(self, text: str) -> IntentDraft:
        payload = self.extractor.extract(
            text,
            schema=IntentDraft.model_json_schema(),
            instructions=intent_instructions(),
        )
        return IntentDraft.model_validate(dict(payload))
