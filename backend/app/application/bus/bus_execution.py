from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class BusExecution(BaseModel):
    """The shared, frozen record of one dispatch through either CommandBus
    or QueryBus — produced exclusively by BusExecutionService. `name` is
    generic on purpose: it's a command name for CommandBus, a query name
    for QueryBus, and this model knows the difference between neither.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    started_at: datetime
    finished_at: datetime
    duration: float
    success: bool
    payload: Any | None = None
    reason: str | None = None
