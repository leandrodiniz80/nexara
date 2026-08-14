from pydantic import BaseModel, Field


class NextActionResult(BaseModel):
    """What every NextActionService.recommend_next_action() call returns — the
    same "always a result, never a raised exception past this boundary"
    shape as every other *Result type in this codebase. `recommended_action`/
    `recommended_stage`/`priority` are all plain strings, never a new enum:
    a closed vocabulary here would be one more thing a future pipeline
    change would need to keep in sync, whereas a stage *name* is already the
    single source of truth CRMStage itself carries.
    """

    success: bool
    recommended_action: str | None = None
    recommended_stage: str | None = None
    priority: str | None = None
    reason: str | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    execution_time: float
