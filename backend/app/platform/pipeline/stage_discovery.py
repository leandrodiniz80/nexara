from abc import ABC, abstractmethod

from app.platform.pipeline.pipeline_stage import PipelineStage


class StageDiscovery(ABC):
    """Supplies the ordered concrete PipelineStage classes a StageProvider
    should instantiate, without the caller ever needing to know which
    classes exist. DefaultStageProvider depends only on this contract.
    """

    @abstractmethod
    def discover(self) -> tuple[type[PipelineStage], ...]:
        ...
