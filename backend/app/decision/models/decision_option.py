from typing import Any

from pydantic import BaseModel, ConfigDict


class DecisionOption(BaseModel):
    """One candidate a Strategy proposes for a decision. DecisionEngine never
    invents options itself — it only chooses the best-scoring one among what its
    registered Strategies return. Frozen: a Strategy always produces a fresh
    DecisionOption rather than mutating one in place.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    score: float
    reason: str | None = None
    payload: Any | None = None
