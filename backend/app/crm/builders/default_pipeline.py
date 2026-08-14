from app.crm.builders.pipeline_builder import PipelineBuilder
from app.crm.models.crm_pipeline import CRMPipeline
from app.crm.models.enums import OpportunityStatus


def build_default_pipeline() -> CRMPipeline:
    """Lead -> Contato -> Reunião -> Proposta -> Negociação -> Fechado (won) /
    Perdido (lost) — the platform's standard commercial pipeline."""
    stages = [
        PipelineBuilder.build_stage(name="Lead", order=1),
        PipelineBuilder.build_stage(name="Contato", order=2),
        PipelineBuilder.build_stage(name="Reunião", order=3),
        PipelineBuilder.build_stage(name="Proposta", order=4),
        PipelineBuilder.build_stage(name="Negociação", order=5),
        PipelineBuilder.build_stage(name="Fechado", order=6, outcome=OpportunityStatus.WON),
        PipelineBuilder.build_stage(name="Perdido", order=7, outcome=OpportunityStatus.LOST),
    ]
    return PipelineBuilder.build_pipeline(name="Pipeline Comercial", stages=stages)
