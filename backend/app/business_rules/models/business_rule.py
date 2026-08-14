import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.business_rules.models.enums import ComparisonOperator, LogicalOperator, RuleType


class BusinessRule(BaseModel):
    """A generic rule definition — the engine's only unit of work. Frozen: a
    RuleBuilder always produces a fresh BusinessRule rather than mutating one in
    place, the same "definition is immutable" convention as WorkflowStep.

    Depending on `rule_type`, only the matching subset of fields is meaningful:
    COMPARISON uses `field`/`operator`/`value`; LOGICAL uses `logical_operator`/
    `rules` (its child BusinessRules — AND/OR require one or more, NOT requires
    exactly one); EXPRESSION uses `expression`, a raw string like "score >= 70"
    parsed by ExpressionEvaluator. Nothing here encodes what "score" or "Goiânia"
    mean — that meaning lives entirely in whatever RuleContext.variables the
    caller supplies.
    """

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    rule_type: RuleType
    field: str | None = None
    operator: ComparisonOperator | None = None
    value: Any | None = None
    logical_operator: LogicalOperator | None = None
    rules: list["BusinessRule"] = Field(default_factory=list)
    expression: str | None = None
    description: str | None = None


BusinessRule.model_rebuild()
