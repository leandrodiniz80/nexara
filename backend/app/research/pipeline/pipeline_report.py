from typing import Any

from pydantic import BaseModel, Field

from app.research.pipeline.pipeline_result import PipelineResult


class PipelineReport(BaseModel):
    """The execution trace of one LeadDiscoveryPipeline run: which steps completed,
    how long it took, anything worth flagging, and (the one addition beyond the four
    literal fields) the actual `result` — without it, a caller running the pipeline
    would have no way to get the companies it found. `statistics` mirrors `result`'s
    summary numbers as a flat dict, for callers that just want to log/print them
    without touching the full result (e.g. when the run failed and there is no result).
    """

    steps: list[str] = Field(default_factory=list)
    duration: float
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    statistics: dict[str, Any] = Field(default_factory=dict)
    result: PipelineResult | None = None
