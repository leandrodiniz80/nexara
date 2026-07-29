from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class AgentResult(BaseModel):
    """What every AgentBase.execute() call returns, success or failure alike."""

    success: bool
    agent_name: str
    execution_time: float
    provider: str | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: Decimal | None = None
    payload: dict[str, Any] | None = None
    logs: list[str] = Field(default_factory=list)
