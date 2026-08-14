from app.platform.pipeline.default_stage_discovery import DefaultStageDiscovery
from app.platform.pipeline.pipeline_stage import PipelineStage
from app.platform.pipeline.stage_discovery import StageDiscovery
from app.platform.pipeline.stage_provider import StageProvider


class DefaultStageProvider(StageProvider):
    """Knows no concrete PipelineStage class at all. Its only dependency is
    StageDiscovery (DefaultStageDiscovery when not given): it asks it for
    the ordered stage classes, instantiates each with no arguments, and
    returns them. Which stages exist is exclusively StageDiscovery's
    concern now.
    """

    def __init__(self, *, stage_discovery: StageDiscovery | None = None) -> None:
        self._stage_discovery = stage_discovery or DefaultStageDiscovery()

    def stages(self) -> tuple[PipelineStage, ...]:
        return tuple(stage_class() for stage_class in self._stage_discovery.discover())
