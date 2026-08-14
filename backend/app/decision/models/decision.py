from typing import Any

from pydantic import BaseModel, ConfigDict

from app.decision.models.enums import DecisionType


class Decision(BaseModel):
    """The persisted record of one decision actually made — built by
    DecisionEngine.decide() from whichever DecisionOption was selected, once a
    winner among a Strategy's candidates has been picked. Frozen, the same
    "record of what happened" convention as RuleResult in app.business_rules:
    nothing in this sprint mutates one in place after it's created.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    type: DecisionType
    priority: int = 0
    score: float
    payload: Any | None = None
