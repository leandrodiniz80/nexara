import uuid

import pytest

from app.crm.builders.default_pipeline import build_default_pipeline
from app.crm.engine.crm_engine import CRMEngine
from app.crm.models.enums import ActivityType, OpportunityStatus
from app.crm.repositories.activity_repository import ActivityRepository
from app.crm.repositories.company_repository import CompanyRepository
from app.crm.repositories.contact_repository import ContactRepository
from app.crm.repositories.opportunity_repository import OpportunityRepository
from app.crm.repositories.pipeline_repository import PipelineRepository
from app.crm.services.opportunity_lifecycle_service import OpportunityLifecycleService
from app.crm.services.opportunity_lifecycle_service_factory import (
    build_default_opportunity_lifecycle_service,
)


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


def test_move_to_stage_moves_the_opportunity():
    engine, pipeline, opportunity = _engine_with_opportunity()
    service = OpportunityLifecycleService(engine)

    result = service.move_to_stage(opportunity.id, _stage_id(pipeline, "Contato"))

    assert result.success is True
    assert result.opportunity.stage_id == _stage_id(pipeline, "Contato")
    assert result.opportunity.status == OpportunityStatus.OPEN


def test_mark_as_won_moves_the_opportunity_to_the_won_stage():
    engine, pipeline, opportunity = _engine_with_opportunity()
    service = OpportunityLifecycleService(engine)

    result = service.mark_as_won(opportunity.id)

    assert result.success is True
    assert result.opportunity.status == OpportunityStatus.WON
    assert result.opportunity.stage_id == _stage_id(pipeline, "Fechado")
    assert result.warnings == []


def test_mark_as_lost_moves_the_opportunity_to_the_lost_stage():
    engine, pipeline, opportunity = _engine_with_opportunity()
    service = OpportunityLifecycleService(engine)

    result = service.mark_as_lost(opportunity.id)

    assert result.success is True
    assert result.opportunity.status == OpportunityStatus.LOST
    assert result.opportunity.stage_id == _stage_id(pipeline, "Perdido")


def test_close_defaults_to_won():
    engine, pipeline, opportunity = _engine_with_opportunity()
    service = OpportunityLifecycleService(engine)

    result = service.close(opportunity.id)

    assert result.opportunity.status == OpportunityStatus.WON


def test_close_can_be_given_the_lost_outcome():
    engine, pipeline, opportunity = _engine_with_opportunity()
    service = OpportunityLifecycleService(engine)

    result = service.close(opportunity.id, outcome=OpportunityStatus.LOST)

    assert result.opportunity.status == OpportunityStatus.LOST


def test_reopen_moves_a_won_opportunity_back_to_the_first_stage():
    engine, pipeline, opportunity = _engine_with_opportunity()
    service = OpportunityLifecycleService(engine)
    service.mark_as_won(opportunity.id)

    result = service.reopen(opportunity.id)

    assert result.success is True
    assert result.opportunity.status == OpportunityStatus.OPEN
    assert result.opportunity.stage_id == _stage_id(pipeline, "Lead")


def test_schedule_activity_registers_an_activity_against_the_opportunity():
    engine, pipeline, opportunity = _engine_with_opportunity()
    service = OpportunityLifecycleService(engine)

    result = service.schedule_activity(
        opportunity.id, ActivityType.MEETING, notes="Reunião de apresentação"
    )

    assert result.success is True
    assert result.activity is not None
    assert result.activity.opportunity_id == opportunity.id
    assert result.activity.notes == "Reunião de apresentação"
    assert result.opportunity.id == opportunity.id


def test_move_to_a_nonexistent_stage_fails_gracefully():
    engine, pipeline, opportunity = _engine_with_opportunity()
    service = OpportunityLifecycleService(engine)

    result = service.move_to_stage(opportunity.id, uuid.uuid4())

    assert result.success is False
    assert result.opportunity is None
    assert len(result.errors) == 1


@pytest.mark.parametrize(
    "method_name,args",
    [
        ("move_to_stage", (uuid.uuid4(),)),
        ("mark_as_won", ()),
        ("mark_as_lost", ()),
        ("reopen", ()),
    ],
)
def test_operations_on_a_nonexistent_opportunity_fail_gracefully(method_name, args):
    engine, _, _ = _engine_with_opportunity()
    service = OpportunityLifecycleService(engine)
    method = getattr(service, method_name)

    result = method(uuid.uuid4(), *args)

    assert result.success is False
    assert result.opportunity is None
    assert len(result.errors) == 1


def test_schedule_activity_on_a_nonexistent_opportunity_fails_gracefully():
    engine, _, _ = _engine_with_opportunity()
    service = OpportunityLifecycleService(engine)

    result = service.schedule_activity(uuid.uuid4(), ActivityType.CALL)

    assert result.success is False
    assert result.activity is None
    assert len(result.errors) == 1


def test_marking_as_won_twice_warns_but_still_succeeds():
    engine, pipeline, opportunity = _engine_with_opportunity()
    service = OpportunityLifecycleService(engine)
    service.mark_as_won(opportunity.id)

    result = service.mark_as_won(opportunity.id)

    assert result.success is True
    assert any("already marked as won" in warning for warning in result.warnings)


def test_reopening_an_already_open_first_stage_opportunity_warns_but_still_succeeds():
    engine, pipeline, opportunity = _engine_with_opportunity()
    service = OpportunityLifecycleService(engine)

    result = service.reopen(opportunity.id)

    assert result.success is True
    assert any("already at the pipeline's first stage" in warning for warning in result.warnings)


def test_compatibility_the_underlying_crm_engine_state_reflects_every_operation():
    """The service never bypasses or duplicates CRMEngine's own state — every
    change is visible through the exact same CRMEngine/repositories a caller
    already had a reference to."""
    engine, pipeline, opportunity = _engine_with_opportunity()
    service = OpportunityLifecycleService(engine)

    service.move_to_stage(opportunity.id, _stage_id(pipeline, "Proposta"))

    stored = engine.opportunity_repository.get_opportunity(opportunity.id)
    assert stored.stage_id == _stage_id(pipeline, "Proposta")
    assert stored is opportunity  # CRMEngine mutates opportunities in place, unchanged


def test_build_default_opportunity_lifecycle_service_wires_a_real_crm_engine():
    service = build_default_opportunity_lifecycle_service()

    assert isinstance(service, OpportunityLifecycleService)
    assert isinstance(service.crm_engine, CRMEngine)


def test_build_default_opportunity_lifecycle_service_reuses_a_given_engine():
    engine, _, _ = _engine_with_opportunity()

    service = build_default_opportunity_lifecycle_service(crm_engine=engine)

    assert service.crm_engine is engine
