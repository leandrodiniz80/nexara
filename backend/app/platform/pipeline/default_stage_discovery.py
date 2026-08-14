from app.platform.pipeline.decision_stage import DecisionStage
from app.platform.pipeline.observability_stage import ObservabilityStage
from app.platform.pipeline.operations_stage import OperationsStage
from app.platform.pipeline.pipeline_stage import PipelineStage
from app.platform.pipeline.runtime_stage import RuntimeStage
from app.platform.pipeline.stage_discovery import StageDiscovery


class DefaultStageDiscovery(StageDiscovery):
    """The only place in the platform authorized to know the concrete
    OperationsStage/DecisionStage/RuntimeStage/ObservabilityStage classes.
    Every other file that needs the platform's official stage classes goes
    through StageDiscovery instead of importing these directly.
    """

    def discover(self) -> tuple[type[PipelineStage], ...]:
        return (OperationsStage, DecisionStage, RuntimeStage, ObservabilityStage)
