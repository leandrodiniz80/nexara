from typing import Any

from pydantic import BaseModel, Field


class TaskResult(BaseModel):
    """What every TaskExecutor.run() call returns, success or failure alike — same
    "always a result, never a raised exception past this boundary" shape as
    AgentResult (app/ai) and JobResult (app/jobs)."""

    success: bool
    output: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    duration: float
    logs: list[str] = Field(default_factory=list)
