from typing import Any

from pydantic import BaseModel, ConfigDict


class CommandRequest(BaseModel):
    """One request to dispatch a public command through CommandBus —
    frozen. `payload` stays genuinely `Any`: CommandBus never inspects or
    transforms it beyond what forwarding it onward requires.
    """

    model_config = ConfigDict(frozen=True)

    command_name: str
    payload: Any | None = None
    request_id: str | None = None
