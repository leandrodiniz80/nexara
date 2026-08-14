from typing import Any

from pydantic import BaseModel, ConfigDict


class CommandResult(BaseModel):
    """The frozen outcome of dispatching one CommandRequest through
    CommandBus — whether the command was found and run, and whatever it
    returned. `reason` is populated only on failure (e.g. an unknown
    command); `payload` only on success.
    """

    model_config = ConfigDict(frozen=True)

    success: bool
    command_name: str
    payload: Any | None = None
    reason: str | None = None
    execution_time: float
