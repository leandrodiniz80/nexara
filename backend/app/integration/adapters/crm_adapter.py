from app.crm.engine.crm_engine import CRMEngine
from app.crm.models.crm_opportunity import CRMOpportunity


class CRMAdapter:
    """Optional post-step VerticalSlice calls after a successful Workflow run
    — registers the prospected company and a commercial opportunity in the
    real CRMEngine, using its default "Pipeline Comercial" pipeline. Never
    called if the caller passes no CRMAdapter to VerticalSlice: CRM
    registration is entirely optional.
    """

    def __init__(self, crm_engine: CRMEngine) -> None:
        self.crm_engine = crm_engine

    def create_opportunity(self, *, company_name: str, opportunity_title: str) -> CRMOpportunity:
        company = self.crm_engine.create_company(company_name)
        pipeline = self.crm_engine.pipeline_repository.get_by_name("Pipeline Comercial")
        return self.crm_engine.create_opportunity(
            company.id, opportunity_title, pipeline_id=pipeline.id
        )
