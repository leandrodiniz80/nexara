from typing import Any

from pydantic import BaseModel, Field


class ApplicationServiceResult(BaseModel):
    """What every Application Service method returns, success or failure alike —
    same "always a result, never a raised exception past this boundary" shape as
    AgentResult (app/ai), JobResult (app/jobs), and TaskResult (app/application/tasks).
    `data` is intentionally untyped: each service method puts whatever its caller
    needs there (a Response DTO, a domain entity dump, a plain dict)."""

    success: bool
    data: Any | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    execution_time: float
