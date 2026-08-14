from pydantic import BaseModel


class RuleResult(BaseModel):
    """What every RulesEngine.evaluate() call returns — the same "always a
    result, never a raised exception past this boundary" shape as every other
    *Result type in this codebase.
    """

    success: bool
    rule_name: str
    reason: str | None = None
    execution_time: float
