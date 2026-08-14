from app.crm.builders.default_pipeline import build_default_pipeline
from app.crm.engine.crm_engine import CRMEngine
from app.crm.models.crm_pipeline import CRMPipeline
from app.crm.repositories.activity_repository import ActivityRepository
from app.crm.repositories.company_repository import CompanyRepository
from app.crm.repositories.contact_repository import ContactRepository
from app.crm.repositories.opportunity_repository import OpportunityRepository
from app.crm.repositories.pipeline_repository import PipelineRepository


def _engine_with_seeded_pipeline() -> tuple[CRMEngine, CRMPipeline]:
    pipeline_repository = PipelineRepository()
    pipeline = build_default_pipeline()
    pipeline_repository.save_pipeline(pipeline)
    engine = CRMEngine(
        company_repository=CompanyRepository(),
        contact_repository=ContactRepository(),
        opportunity_repository=OpportunityRepository(),
        activity_repository=ActivityRepository(),
        pipeline_repository=pipeline_repository,
    )
    return engine, pipeline


def _stage_id(pipeline, name: str):
    return next(stage.id for stage in pipeline.stages if stage.name == name)


def test_dashboard_on_an_empty_crm_reports_all_zeros():
    engine, _ = _engine_with_seeded_pipeline()

    dashboard = engine.get_dashboard()

    assert dashboard.total_companies == 0
    assert dashboard.total_contacts == 0
    assert dashboard.total_opportunities == 0
    assert dashboard.by_stage == {}
    assert dashboard.won == 0
    assert dashboard.lost == 0
    assert dashboard.conversion_rate == 0.0


def test_dashboard_counts_companies_contacts_and_opportunities():
    engine, pipeline = _engine_with_seeded_pipeline()
    company = engine.create_company("Agência XYZ")
    engine.create_contact(company.id, "João")
    engine.create_opportunity(company.id, "Outdoor Digital", pipeline_id=pipeline.id)

    dashboard = engine.get_dashboard()

    assert dashboard.total_companies == 1
    assert dashboard.total_contacts == 1
    assert dashboard.total_opportunities == 1
    assert dashboard.by_stage == {"Lead": 1}


def test_dashboard_computes_won_lost_and_conversion_rate():
    engine, pipeline = _engine_with_seeded_pipeline()
    company = engine.create_company("Agência XYZ")

    won = engine.create_opportunity(company.id, "Won Deal", pipeline_id=pipeline.id)
    engine.move_stage(won.id, _stage_id(pipeline, "Fechado"))

    lost = engine.create_opportunity(company.id, "Lost Deal", pipeline_id=pipeline.id)
    engine.move_stage(lost.id, _stage_id(pipeline, "Perdido"))

    engine.create_opportunity(company.id, "Open Deal", pipeline_id=pipeline.id)

    dashboard = engine.get_dashboard()

    assert dashboard.won == 1
    assert dashboard.lost == 1
    assert dashboard.total_opportunities == 3
    assert dashboard.conversion_rate == 0.5
    assert dashboard.by_stage == {"Fechado": 1, "Perdido": 1, "Lead": 1}
