from typing import Any

from pydantic import BaseModel, Field


class OrchestrationContext(BaseModel):
    """Everything one Orchestrator.orchestrate() call needs. `variables` is
    threaded, unchanged, through every port (Decision, Rules, Runtime,
    Observability) — the Orchestrator never reads or interprets it itself, only
    the concrete port implementations eventually will.
    """

    variables: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None
