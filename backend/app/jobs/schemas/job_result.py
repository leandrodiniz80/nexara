from typing import Any

from pydantic import BaseModel, Field


class JobResult(BaseModel):
    """What a JobExecutor.execute() call returns, success or failure alike — the Job
    module's counterpart to app.research.pipeline's PipelineResult and app.ai's
    AgentResult."""

    success: bool
    duration: float
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    output: dict[str, Any] | None = None
