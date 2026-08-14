import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.operations.history.operation_history_event import OperationHistoryEvent


class OperationTrace(BaseModel):
    """Observability's own frozen record of one Operation's complete
    execution — built once, from an already-finished OperationHistory and
    OperationResult, never mutated afterward.
    """

    model_config = ConfigDict(frozen=True)

    operation_id: uuid.UUID
    started_at: datetime
    finished_at: datetime
    duration: float
    success: bool
    events: tuple[OperationHistoryEvent, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)
