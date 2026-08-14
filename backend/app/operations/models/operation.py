import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.operations.models.enums import OperationState


class Operation(BaseModel):
    """One unit of operational work tracked by the platform — frozen: the
    record of an operation at one point in time. OperationsEngine always
    returns a new Operation reflecting a state transition (start/finish/
    fail); it never mutates a previous one in place.
    """

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    status: OperationState = OperationState.PENDING
    metadata: dict[str, Any] = Field(default_factory=dict)
