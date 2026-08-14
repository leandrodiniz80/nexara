from typing import Any

from pydantic import BaseModel, Field


class RuleContext(BaseModel):
    """Everything one RulesEngine.evaluate() call needs — the facts a rule is
    checked against. `variables` is the generic "field name -> value" bag every
    ComparisonEvaluator/ExpressionEvaluator reads from; the engine itself never
    knows what any of those field names mean.
    """

    variables: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None
