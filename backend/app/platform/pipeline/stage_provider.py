from abc import ABC, abstractmethod

from app.platform.pipeline.pipeline_stage import PipelineStage


class StageProvider(ABC):
    """Supplies the ordered PipelineStages a PipelineRegistry should be
    built with, without the caller ever needing to know which concrete
    stages exist. PipelineRegistryFactory depends only on this contract.
    """

    @abstractmethod
    def stages(self) -> tuple[PipelineStage, ...]:
        ...
