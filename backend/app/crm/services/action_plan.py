from datetime import date

from pydantic import BaseModel, Field


class ActionPlan(BaseModel):
    """What every ActionPlanningService.plan() call returns — the same
    "always a result, never a raised exception past this boundary" shape as
    every other *Result type in this codebase. `recommended_date` is a plain
    calendar date, always computed, never persisted anywhere by this class.
    """

    success: bool
    recommended_action: str | None = None
    recommended_date: date | None = None
    recommended_time_window: str | None = None
    recommended_priority: str | None = None
    estimated_duration: int | None = None
    reason: str | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    execution_time: float
