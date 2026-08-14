import uuid

from pydantic import BaseModel

from app.crm.models.crm_pipeline import CRMPipeline


class PipelineSummary(BaseModel):
    """A read-friendly view of a CRMPipeline's shape — how many stages, in what
    order, without exposing each CRMStage's full id/outcome."""

    id: uuid.UUID
    name: str
    stage_count: int
    stage_names: list[str]

    @classmethod
    def from_pipeline(cls, pipeline: CRMPipeline) -> "PipelineSummary":
        ordered = sorted(pipeline.stages, key=lambda stage: stage.order)
        return cls(
            id=pipeline.id,
            name=pipeline.name,
            stage_count=len(ordered),
            stage_names=[stage.name for stage in ordered],
        )
