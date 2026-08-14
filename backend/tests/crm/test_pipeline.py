import uuid

import pytest

from app.crm.builders.default_pipeline import build_default_pipeline
from app.crm.builders.pipeline_builder import PipelineBuilder
from app.crm.engine.crm_engine import CRMEngine
from app.crm.exceptions.crm_exceptions import PipelineNotFoundError, StageNotFoundError
from app.crm.models.enums import OpportunityStatus
from app.crm.repositories.activity_repository import ActivityRepository
from app.crm.repositories.company_repository import CompanyRepository
from app.crm.repositories.contact_repository import ContactRepository
from app.crm.repositories.opportunity_repository import OpportunityRepository
from app.crm.repositories.pipeline_repository import PipelineRepository


def test_default_pipeline_has_the_seven_standard_stages_in_order():
    pipeline = build_default_pipeline()

    ordered = sorted(pipeline.stages, key=lambda stage: stage.order)
    assert [stage.name for stage in ordered] == [
        "Lead",
        "Contato",
        "Reunião",
        "Proposta",
        "Negociação",
        "Fechado",
        "Perdido",
    ]


def test_default_pipeline_fechado_is_won_and_perdido_is_lost():
    pipeline = build_default_pipeline()

    by_name = {stage.name: stage for stage in pipeline.stages}
    assert by_name["Fechado"].outcome == OpportunityStatus.WON
    assert by_name["Perdido"].outcome == OpportunityStatus.LOST
    assert by_name["Lead"].outcome == OpportunityStatus.OPEN


def test_pipeline_builder_builds_a_custom_pipeline():
    stage = PipelineBuilder.build_stage(name="Custom Stage", order=1)
    pipeline = PipelineBuilder.build_pipeline(name="Custom Pipeline", stages=[stage])

    assert pipeline.name == "Custom Pipeline"
    assert pipeline.stages == [stage]


def _engine() -> CRMEngine:
    return CRMEngine(
        company_repository=CompanyRepository(),
        contact_repository=ContactRepository(),
        opportunity_repository=OpportunityRepository(),
        activity_repository=ActivityRepository(),
        pipeline_repository=PipelineRepository(),
    )


def test_list_pipeline_returns_stages_in_order_regardless_of_insertion_order():
    engine = _engine()
    stages = [
        PipelineBuilder.build_stage(name="Second", order=2),
        PipelineBuilder.build_stage(name="First", order=1),
    ]
    pipeline = PipelineBuilder.build_pipeline(name="Test Pipeline", stages=stages)
    engine.pipeline_repository.save_pipeline(pipeline)

    ordered = engine.list_pipeline(pipeline.id)

    assert [stage.name for stage in ordered] == ["First", "Second"]


def test_list_pipeline_for_unknown_pipeline_raises():
    engine = _engine()

    with pytest.raises(PipelineNotFoundError):
        engine.list_pipeline(uuid.uuid4())


def test_move_stage_to_an_unknown_stage_raises():
    engine = _engine()
    pipeline = build_default_pipeline()
    engine.pipeline_repository.save_pipeline(pipeline)
    company = engine.create_company("Agência XYZ")
    opportunity = engine.create_opportunity(company.id, "Outdoor Digital", pipeline_id=pipeline.id)

    with pytest.raises(StageNotFoundError):
        engine.move_stage(opportunity.id, uuid.uuid4())
