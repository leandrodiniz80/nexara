import uuid

from app.crm.builders.default_pipeline import build_default_pipeline
from app.crm.builders.pipeline_builder import PipelineBuilder
from app.crm.engine.crm_engine import CRMEngine
from app.crm.models.enums import ActivityType, OpportunityStatus
from app.crm.repositories.activity_repository import ActivityRepository
from app.crm.repositories.company_repository import CompanyRepository
from app.crm.repositories.contact_repository import ContactRepository
from app.crm.repositories.opportunity_repository import OpportunityRepository
from app.crm.repositories.pipeline_repository import PipelineRepository
from app.crm.services.next_action_service import NextActionService
from app.crm.services.next_action_service_factory import build_default_next_action_service


def _engine_with_opportunity():
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
    company = engine.create_company("Agência XYZ")
    opportunity = engine.create_opportunity(company.id, "Outdoor Digital", pipeline_id=pipeline.id)
    return engine, pipeline, opportunity


def _stage_id(pipeline, name: str) -> uuid.UUID:
    return next(stage.id for stage in pipeline.stages if stage.name == name)


def test_lead_novo_recommends_first_contact():
    engine, pipeline, opportunity = _engine_with_opportunity()
    service = NextActionService(engine)

    result = service.recommend_next_action(opportunity.id)

    assert result.success is True
    assert result.recommended_action == "Realizar primeiro contato"
    assert result.recommended_stage == "Contato"
    assert result.priority == "high"


def test_contato_realizado_recommends_scheduling_a_meeting():
    engine, pipeline, opportunity = _engine_with_opportunity()
    engine.move_stage(opportunity.id, _stage_id(pipeline, "Contato"))
    engine.register_activity(opportunity.id, ActivityType.CALL, notes="Primeiro contato feito")
    service = NextActionService(engine)

    result = service.recommend_next_action(opportunity.id)

    assert result.success is True
    assert result.recommended_action == "Agendar reunião"
    assert result.recommended_stage == "Reunião"
    assert result.warnings == []


def test_reuniao_realizada_recommends_sending_a_proposal():
    engine, pipeline, opportunity = _engine_with_opportunity()
    engine.move_stage(opportunity.id, _stage_id(pipeline, "Reunião"))
    engine.register_activity(opportunity.id, ActivityType.MEETING)
    service = NextActionService(engine)

    result = service.recommend_next_action(opportunity.id)

    assert result.success is True
    assert result.recommended_action == "Enviar proposta"
    assert result.recommended_stage == "Proposta"


def test_proposta_enviada_recommends_a_follow_up():
    engine, pipeline, opportunity = _engine_with_opportunity()
    engine.move_stage(opportunity.id, _stage_id(pipeline, "Proposta"))
    engine.register_activity(opportunity.id, ActivityType.EMAIL)
    service = NextActionService(engine)

    result = service.recommend_next_action(opportunity.id)

    assert result.success is True
    assert result.recommended_action == "Executar follow-up"
    assert result.recommended_stage == "Negociação"


def test_follow_up_realizado_recommends_waiting_for_a_response():
    engine, pipeline, opportunity = _engine_with_opportunity()
    engine.move_stage(opportunity.id, _stage_id(pipeline, "Negociação"))
    engine.register_activity(opportunity.id, ActivityType.CALL, notes="Follow-up realizado")
    service = NextActionService(engine)

    result = service.recommend_next_action(opportunity.id)

    assert result.success is True
    assert result.recommended_action == "Aguardar resposta"
    assert result.recommended_stage == "Fechado"
    assert result.priority == "low"


def test_oportunidade_ganha_recommends_no_action():
    engine, pipeline, opportunity = _engine_with_opportunity()
    engine.move_stage(opportunity.id, _stage_id(pipeline, "Fechado"))
    service = NextActionService(engine)

    result = service.recommend_next_action(opportunity.id)

    assert result.success is True
    assert result.recommended_action == "Nenhuma ação"
    assert result.recommended_stage is None
    assert "won" in result.reason


def test_oportunidade_perdida_recommends_no_action():
    engine, pipeline, opportunity = _engine_with_opportunity()
    engine.move_stage(opportunity.id, _stage_id(pipeline, "Perdido"))
    service = NextActionService(engine)

    result = service.recommend_next_action(opportunity.id)

    assert result.success is True
    assert result.recommended_action == "Nenhuma ação"
    assert result.recommended_stage is None
    assert "lost" in result.reason


def test_pipeline_without_the_expected_stage_fails_gracefully():
    pipeline_repository = PipelineRepository()
    custom_stage = PipelineBuilder.build_stage(name="Estágio Customizado", order=1)
    pipeline = PipelineBuilder.build_pipeline(name="Custom Pipeline", stages=[custom_stage])
    pipeline_repository.save_pipeline(pipeline)
    engine = CRMEngine(
        company_repository=CompanyRepository(),
        contact_repository=ContactRepository(),
        opportunity_repository=OpportunityRepository(),
        activity_repository=ActivityRepository(),
        pipeline_repository=pipeline_repository,
    )
    company = engine.create_company("Agência XYZ")
    opportunity = engine.create_opportunity(company.id, "Outdoor Digital", pipeline_id=pipeline.id)
    service = NextActionService(engine)

    result = service.recommend_next_action(opportunity.id)

    assert result.success is False
    assert result.recommended_action is None
    assert len(result.errors) == 1


def test_nonexistent_opportunity_fails_gracefully():
    engine, _, _ = _engine_with_opportunity()
    service = NextActionService(engine)

    result = service.recommend_next_action(uuid.uuid4())

    assert result.success is False
    assert result.recommended_action is None
    assert len(result.errors) == 1


def test_warning_when_no_activity_has_been_logged_yet():
    engine, pipeline, opportunity = _engine_with_opportunity()
    engine.move_stage(opportunity.id, _stage_id(pipeline, "Contato"))
    service = NextActionService(engine)

    result = service.recommend_next_action(opportunity.id)

    assert result.success is True
    assert any("No activity has been logged" in warning for warning in result.warnings)


def test_no_activity_warning_is_skipped_for_a_brand_new_lead():
    """A lead with zero activities is the expected, unremarkable state — it
    should not be treated as a warning-worthy gap."""
    engine, pipeline, opportunity = _engine_with_opportunity()
    service = NextActionService(engine)

    result = service.recommend_next_action(opportunity.id)

    assert result.warnings == []


def test_warning_when_no_next_stage_exists_after_the_current_one():
    pipeline_repository = PipelineRepository()
    lead_stage = PipelineBuilder.build_stage(name="Lead", order=1)
    distant_stage = PipelineBuilder.build_stage(name="Negociação", order=5)
    pipeline = PipelineBuilder.build_pipeline(
        name="Gapped Pipeline", stages=[lead_stage, distant_stage]
    )
    pipeline_repository.save_pipeline(pipeline)
    engine = CRMEngine(
        company_repository=CompanyRepository(),
        contact_repository=ContactRepository(),
        opportunity_repository=OpportunityRepository(),
        activity_repository=ActivityRepository(),
        pipeline_repository=pipeline_repository,
    )
    company = engine.create_company("Agência XYZ")
    opportunity = engine.create_opportunity(company.id, "Outdoor Digital", pipeline_id=pipeline.id)
    service = NextActionService(engine)

    result = service.recommend_next_action(opportunity.id)

    assert result.success is True
    assert result.recommended_action == "Realizar primeiro contato"
    assert result.recommended_stage is None
    assert any("No next stage found" in warning for warning in result.warnings)


def test_build_default_next_action_service_wires_a_real_crm_engine():
    service = build_default_next_action_service()

    assert isinstance(service, NextActionService)
    assert isinstance(service.crm_engine, CRMEngine)


def test_build_default_next_action_service_reuses_a_given_engine():
    engine, _, _ = _engine_with_opportunity()

    service = build_default_next_action_service(crm_engine=engine)

    assert service.crm_engine is engine
