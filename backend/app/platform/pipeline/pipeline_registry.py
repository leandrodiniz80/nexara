from pydantic import BaseModel, ConfigDict, Field

from app.platform.pipeline.pipeline_stage import PipelineStage


class PipelineRegistry(BaseModel):
    """The platform's frozen registry of PipelineStages — pure lookup,
    nothing else: it never executes a stage, never knows any concrete
    stage's domain (not Operations, Decision, Runtime, or Observability),
    and never mutates in place. `register()`/`register_many()` always
    return a new PipelineRegistry with the given stage(s) appended to the
    end of the previous, unedited list.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    stages: tuple[PipelineStage, ...] = Field(default_factory=tuple)

    def register(self, stage: PipelineStage) -> "PipelineRegistry":
        return PipelineRegistry(stages=self.stages + (stage,))

    def register_many(self, stages: list[PipelineStage]) -> "PipelineRegistry":
        return PipelineRegistry(stages=self.stages + tuple(stages))

    def list(self) -> list[PipelineStage]:
        return list(self.stages)

    def find(self, name: str) -> PipelineStage | None:
        for stage in self.stages:
            if stage.name() == name:
                return stage
        return None

    def exists(self, name: str) -> bool:
        return self.find(name) is not None
