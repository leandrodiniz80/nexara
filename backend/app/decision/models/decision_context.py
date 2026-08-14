from typing import Any

from pydantic import BaseModel, Field


class DecisionContext(BaseModel):
    """Everything one DecisionEngine.decide() call needs. `variables` is the
    generic bag every Strategy reads its own candidates out of; the engine
    itself never knows what any of those variables mean.
    """

    variables: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None
