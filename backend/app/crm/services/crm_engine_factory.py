from app.crm.builders.default_pipeline import build_default_pipeline
from app.crm.engine.crm_engine import CRMEngine
from app.crm.repositories.activity_repository import ActivityRepository
from app.crm.repositories.company_repository import CompanyRepository
from app.crm.repositories.contact_repository import ContactRepository
from app.crm.repositories.opportunity_repository import OpportunityRepository
from app.crm.repositories.pipeline_repository import PipelineRepository


def build_default_crm_engine(
    *,
    company_repository: CompanyRepository | None = None,
    contact_repository: ContactRepository | None = None,
    opportunity_repository: OpportunityRepository | None = None,
    activity_repository: ActivityRepository | None = None,
    pipeline_repository: PipelineRepository | None = None,
) -> CRMEngine:
    """Composition root for this module — seeds the default "Pipeline Comercial"
    into the PipelineRepository if it's empty, the same "seed if empty" pattern
    build_default_workflow_engine()/build_default_automation_engine() already use.
    """
    pipeline_repository = pipeline_repository or PipelineRepository()
    if not pipeline_repository.list_pipelines():
        pipeline_repository.save_pipeline(build_default_pipeline())

    return CRMEngine(
        company_repository=company_repository or CompanyRepository(),
        contact_repository=contact_repository or ContactRepository(),
        opportunity_repository=opportunity_repository or OpportunityRepository(),
        activity_repository=activity_repository or ActivityRepository(),
        pipeline_repository=pipeline_repository,
    )
