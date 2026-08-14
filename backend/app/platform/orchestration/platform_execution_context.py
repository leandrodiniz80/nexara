from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PlatformExecutionContext(BaseModel):
    """One request to run the platform's full composed pipeline — frozen.
    `payload` stays genuinely `Any`: PlatformExecutionOrchestrator forwards
    it, unpacked exactly as RuntimeEngine.execute() already requires
    (an `(ExecutionType, ExecutionContext)` pair), the same "generic
    payload the caller shapes for whatever it's addressed to" convention
    CommandBus/handlers already use.
    """

    model_config = ConfigDict(frozen=True)

    request_id: str | None = None
    payload: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
