import uuid

from app.crm.models.crm_pipeline import CRMPipeline


class PipelineRepository:
    """In-memory store of every CRMPipeline."""

    def __init__(self) -> None:
        self._pipelines: dict[uuid.UUID, CRMPipeline] = {}

    def save_pipeline(self, pipeline: CRMPipeline) -> CRMPipeline:
        self._pipelines[pipeline.id] = pipeline
        return pipeline

    def get_pipeline(self, pipeline_id: uuid.UUID) -> CRMPipeline | None:
        return self._pipelines.get(pipeline_id)

    def get_by_name(self, name: str) -> CRMPipeline | None:
        return next((p for p in self._pipelines.values() if p.name == name), None)

    def list_pipelines(self) -> list[CRMPipeline]:
        return list(self._pipelines.values())
