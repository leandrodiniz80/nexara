from pydantic import BaseModel, Field

from app.decision.models.decision_option import DecisionOption


class DecisionResult(BaseModel):
    """What every DecisionEngine.decide() call returns — the same "always a
    result, never a raised exception past this boundary" shape as every other
    *Result type in this codebase. `selected_option` is None when nothing could
    be decided (no Strategy found, or it returned no candidates) — `success`
    tells a caller which case it is without guessing from a None check alone.
    """

    selected_option: DecisionOption | None = None
    candidate_options: list[DecisionOption] = Field(default_factory=list)
    execution_time: float
    success: bool
    reason: str | None = None
