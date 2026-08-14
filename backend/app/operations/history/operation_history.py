import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.operations.history.operation_history_event import OperationHistoryEvent


class OperationHistory(BaseModel):
    """The full chronological trail of one Operation — frozen:
    OperationHistoryService never edits an OperationHistory in place, it
    always returns a new one with one more event appended to the end of
    the previous, unedited list of events.
    """

    model_config = ConfigDict(frozen=True)

    operation_id: uuid.UUID
    events: tuple[OperationHistoryEvent, ...] = Field(default_factory=tuple)
