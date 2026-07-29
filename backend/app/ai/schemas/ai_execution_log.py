import uuid
from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, Field


class AIExecutionLog(BaseModel):
    """One audit-trail row for an agent execution. In-memory only for now (kept by
    AIOrchestrator.register_execution()) — swap in a persisted repository later without
    changing this shape or the orchestrator's public methods."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    agent_name: str
    provider: str | None = None
    model: str | None = None
    execution_time: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: Decimal | None = None
    success: bool
