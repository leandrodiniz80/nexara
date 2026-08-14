from app.platform.pipeline.operations_stage import OperationsStage
from app.platform.pipeline.pipeline_stage import PipelineStage
from app.platform.pipeline.stage_provider import StageProvider


class OperationsStageProvider(StageProvider):
    """Supplies exclusively OperationsStage — the only PipelineStage
    Operations is responsible for. Knows nothing about DecisionStage,
    RuntimeStage, or ObservabilityStage.
    """

    def __init__(self, *, operations_stage: OperationsStage | None = None) -> None:
        self._operations_stage = operations_stage or OperationsStage()

    def stages(self) -> tuple[PipelineStage, ...]:
        return (self._operations_stage,)
