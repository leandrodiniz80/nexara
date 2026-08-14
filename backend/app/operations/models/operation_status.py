import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OperationStatus(BaseModel):
    """A live status snapshot for one Operation — frozen: OperationsEngine
    always builds a new OperationStatus to reflect a change, never mutates
    a previous one in place.
    """

    model_config = ConfigDict(frozen=True)

    operation_id: uuid.UUID
    running: bool
    progress: float
    message: str | None = None
    updated_at: datetime
