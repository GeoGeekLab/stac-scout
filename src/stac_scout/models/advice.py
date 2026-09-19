from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .request import ScoutRequest
from .task import DerivedRequirement, GeoTask, TaskProfile


class TaskAdvice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_type: GeoTask
    profile: TaskProfile
    enriched_request: ScoutRequest
    derivations: tuple[DerivedRequirement, ...] = ()
    follow_up_requirements: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
