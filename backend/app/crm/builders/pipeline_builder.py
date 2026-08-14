from app.crm.models.crm_pipeline import CRMPipeline
from app.crm.models.crm_stage import CRMStage
from app.crm.models.enums import OpportunityStatus


class PipelineBuilder:
    """Constructs CRMStages and CRMPipelines — the only place stage/pipeline
    construction logic lives, the same role WorkflowBuilder plays for Workflow."""

    @staticmethod
    def build_stage(
        *, name: str, order: int, outcome: OpportunityStatus = OpportunityStatus.OPEN
    ) -> CRMStage:
        return CRMStage(name=name, order=order, outcome=outcome)

    @staticmethod
    def build_pipeline(*, name: str, stages: list[CRMStage]) -> CRMPipeline:
        return CRMPipeline(name=name, stages=stages)
