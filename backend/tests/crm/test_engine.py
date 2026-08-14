import uuid

import pytest

from app.crm.builders.default_pipeline import build_default_pipeline
from app.crm.engine.crm_engine import CRMEngine
from app.crm.exceptions.crm_exceptions import CompanyNotFoundError, OpportunityNotFoundError
from app.crm.models.crm_pipeline import CRMPipeline
from app.crm.models.enums import ActivityType, OpportunityStatus
from app.crm.repositories.activity_repository import ActivityRepository
from app.crm.repositories.company_repository import CompanyRepository
from app.crm.repositories.contact_repository import ContactRepository
from app.crm.repositories.opportunity_repository import OpportunityRepository
from app.crm.repositories.pipeline_repository import PipelineRepository


def _engine() -> tuple[CRMEngine, CRMPipeline]:
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


def test_create_company_saves_it_in_the_repository():
    engine, _ = _engine()

    company = engine.create_company("Agência XYZ", segment="Publicidade", city="Goiânia")

    assert company.name == "Agência XYZ"
    assert engine.company_repository.get_company(company.id) is company


def test_create_contact_requires_an_existing_company():
    engine, _ = _engine()

    with pytest.raises(CompanyNotFoundError):
        engine.create_contact(uuid.uuid4(), "João")


def test_create_contact_saves_it_linked_to_the_company():
    engine, _ = _engine()
    company = engine.create_company("Agência XYZ")

    contact = engine.create_contact(company.id, "João", role="Diretor de Marketing")

    assert contact.company_id == company.id
    assert engine.contact_repository.get_contact(contact.id) is contact


def test_create_opportunity_starts_in_the_pipelines_first_stage():
    engine, pipeline = _engine()
    company = engine.create_company("Agência XYZ")

    opportunity = engine.create_opportunity(company.id, "Outdoor Digital", pipeline_id=pipeline.id)

    assert opportunity.stage_id == _stage_id(pipeline, "Lead")
    assert opportunity.status == OpportunityStatus.OPEN
    assert engine.opportunity_repository.get_opportunity(opportunity.id) is opportunity


def test_create_opportunity_requires_an_existing_company():
    engine, pipeline = _engine()

    with pytest.raises(CompanyNotFoundError):
        engine.create_opportunity(uuid.uuid4(), "Outdoor Digital", pipeline_id=pipeline.id)


def test_move_stage_updates_stage_and_status():
    engine, pipeline = _engine()
    company = engine.create_company("Agência XYZ")
    opportunity = engine.create_opportunity(company.id, "Outdoor Digital", pipeline_id=pipeline.id)

    moved = engine.move_stage(opportunity.id, _stage_id(pipeline, "Contato"))

    assert moved.stage_id == _stage_id(pipeline, "Contato")
    assert moved.status == OpportunityStatus.OPEN


def test_move_stage_to_fechado_marks_the_opportunity_won():
    engine, pipeline = _engine()
    company = engine.create_company("Agência XYZ")
    opportunity = engine.create_opportunity(company.id, "Outdoor Digital", pipeline_id=pipeline.id)

    moved = engine.move_stage(opportunity.id, _stage_id(pipeline, "Fechado"))

    assert moved.status == OpportunityStatus.WON


def test_move_stage_for_an_unknown_opportunity_raises():
    engine, pipeline = _engine()

    with pytest.raises(OpportunityNotFoundError):
        engine.move_stage(uuid.uuid4(), _stage_id(pipeline, "Contato"))


def test_register_activity_requires_an_existing_opportunity():
    engine, _ = _engine()

    with pytest.raises(OpportunityNotFoundError):
        engine.register_activity(uuid.uuid4(), ActivityType.CALL)


def test_register_activity_saves_it_linked_to_the_opportunity():
    engine, pipeline = _engine()
    company = engine.create_company("Agência XYZ")
    opportunity = engine.create_opportunity(company.id, "Outdoor Digital", pipeline_id=pipeline.id)

    activity = engine.register_activity(
        opportunity.id, ActivityType.MEETING, notes="Reunião de apresentação"
    )

    assert activity.opportunity_id == opportunity.id
    assert engine.activity_repository.get_activity(activity.id) is activity


def test_full_prospect_to_negotiation_journey():
    """The spec's own worked example: Agência XYZ / João / Outdoor Digital, moved
    Lead -> Contato -> Reunião -> Proposta."""
    engine, pipeline = _engine()

    company = engine.create_company("Agência XYZ")
    contact = engine.create_contact(company.id, "João")
    opportunity = engine.create_opportunity(
        company.id, "Outdoor Digital", pipeline_id=pipeline.id, contact_id=contact.id
    )
    assert opportunity.stage_id == _stage_id(pipeline, "Lead")

    engine.move_stage(opportunity.id, _stage_id(pipeline, "Contato"))
    engine.move_stage(opportunity.id, _stage_id(pipeline, "Reunião"))
    moved = engine.move_stage(opportunity.id, _stage_id(pipeline, "Proposta"))

    assert moved.stage_id == _stage_id(pipeline, "Proposta")
    assert moved.status == OpportunityStatus.OPEN
    assert moved.contact_id == contact.id
