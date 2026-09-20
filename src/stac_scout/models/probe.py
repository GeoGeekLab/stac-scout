from __future__ import annotations

from datetime import datetime as DateTime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .dataset import ConstraintCheck
from .report import VerificationStatus


class SearchCompleteness(StrEnum):
    COMPLETE = "complete"
    CAPPED = "capped"
    UNKNOWN = "unknown"


class SearchObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_items: int | None = Field(default=None, gt=0)
    items_observed: int = Field(default=0, ge=0)
    items_retained: int = Field(default=0, ge=0)
    completeness: SearchCompleteness = SearchCompleteness.UNKNOWN
    pagination_exhausted: bool | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def validate_counts(self) -> SearchObservation:
        if self.items_retained > self.items_observed:
            raise ValueError("items_retained cannot exceed items_observed")
        if self.max_items is not None and self.items_observed > self.max_items:
            raise ValueError("items_observed cannot exceed max_items")
        if self.completeness is SearchCompleteness.COMPLETE:
            if self.max_items is not None and self.items_observed >= self.max_items:
                raise ValueError("complete search must end before max_items")
            if self.pagination_exhausted is False:
                raise ValueError("complete search cannot mark pagination as unexhausted")
        if self.completeness is SearchCompleteness.CAPPED:
            if self.max_items is None or self.items_observed != self.max_items:
                raise ValueError("capped search must observe exactly max_items")
            if self.pagination_exhausted is True:
                raise ValueError("capped search cannot prove pagination exhaustion")
        return self

    @classmethod
    def from_counts(
        cls,
        *,
        max_items: int,
        items_observed: int,
        items_retained: int,
    ) -> SearchObservation:
        if items_observed < max_items:
            return cls(
                max_items=max_items,
                items_observed=items_observed,
                items_retained=items_retained,
                completeness=SearchCompleteness.COMPLETE,
                pagination_exhausted=True,
                reason="Item Search ended before the configured result cap",
            )
        return cls(
            max_items=max_items,
            items_observed=items_observed,
            items_retained=items_retained,
            completeness=SearchCompleteness.CAPPED,
            pagination_exhausted=False,
            reason=(
                "Item Search reached the configured result cap; "
                "additional matching Items may exist"
            ),
        )


class ItemEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str
    datetime: DateTime | None = None
    coverage_ratio: float | None = Field(default=None, ge=0, le=1)
    item_fraction_read: float | None = Field(default=None, ge=0, le=1)
    cloud_cover: float | None = Field(default=None, ge=0, le=100)
    asset_keys: tuple[str, ...] = ()


class AvailabilityProbe(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: VerificationStatus
    items_checked: int = Field(ge=0)
    max_coverage_ratio: float | None = Field(default=None, ge=0, le=1)
    items: tuple[ItemEvidence, ...] = ()
    constraints: tuple[ConstraintCheck, ...] = ()
    search: SearchObservation = Field(default_factory=SearchObservation)
    warnings: tuple[str, ...] = ()
