import inspect
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.crm.models.crm_opportunity import CRMOpportunity
from app.crm.services import sales_timeline_service
from app.crm.services.sales_cadence import SalesCadence
from app.crm.services.sales_cadence_execution_service import SalesCadenceExecutionService
from app.crm.services.sales_cadence_step import SalesCadenceStep
from app.crm.services.sales_enrollment_service import SalesEnrollmentService
from app.crm.services.sales_playbook import SalesPlaybook
from app.crm.services.sales_timeline import SalesTimeline
from app.crm.services.sales_timeline_service import SalesTimelineService
from app.crm.services.sales_timeline_service_factory import (
    build_default_sales_timeline_service,
)

_T0 = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)

_STEPS = [
    SalesCadenceStep(
        step_number=1, action="Primeiro e-mail", recommended_delay=0, channel="E-mail", goal="g1"
    ),
    SalesCadenceStep(
        step_number=2, action="WhatsApp", recommended_delay=2, channel="WhatsApp", goal="g2"
    ),
]


def _opportunity() -> CRMOpportunity:
    return CRMOpportunity(
        company_id=uuid.uuid4(),
        title="Outdoor Digital",
        pipeline_id=uuid.uuid4(),
        stage_id=uuid.uuid4(),
    )


def _playbook() -> SalesPlaybook:
    return SalesPlaybook(
        name="Cadência Comercial Padrão",
        description="Abordagem comercial padrão.",
        target_segment="Publicidade",
        company_size="Qualquer",
        priority="ALTA",
        cadence_name="Cadência Comercial Padrão",
        estimated_duration=12,
        recommended_channels=["E-mail", "WhatsApp"],
    )


def _cadence() -> SalesCadence:
    return SalesCadence(
        steps=list(_STEPS), total_steps=len(_STEPS), current_step=_STEPS[0], next_step=_STEPS[1]
    )


def _enrollment():
    enrollment_service = SalesEnrollmentService(SalesCadenceExecutionService())
    return enrollment_service.enroll(_opportunity(), _playbook(), _cadence(), now=_T0)


def test_timeline_criada_vazia():
    service = SalesTimelineService()

    timeline = service.create(_enrollment(), now=_T0)

    assert isinstance(timeline, SalesTimeline)
    assert timeline.events == []
    assert timeline.created_at == _T0
    assert timeline.last_updated == _T0


def test_record_started_adds_exactly_one_event():
    service = SalesTimelineService()
    timeline = service.create(_enrollment(), now=_T0)

    updated = service.record_started(timeline, step=_STEPS[0], now=_T0 + timedelta(minutes=1))

    assert len(updated.events) == 1
    event = updated.events[0]
    assert event.event_type == "started"
    assert event.step_number == 1
    assert event.step_name == "Primeiro e-mail"


def test_record_step_completed_adds_the_step_details():
    service = SalesTimelineService()
    timeline = service.create(_enrollment(), now=_T0)

    updated = service.record_step_completed(
        timeline, _STEPS[0], now=_T0 + timedelta(minutes=2)
    )

    event = updated.events[-1]
    assert event.event_type == "step_completed"
    assert event.step_number == 1
    assert event.step_name == "Primeiro e-mail"


def test_record_step_rolled_back_adds_the_step_details():
    service = SalesTimelineService()
    timeline = service.create(_enrollment(), now=_T0)

    updated = service.record_step_rolled_back(
        timeline, _STEPS[0], now=_T0 + timedelta(minutes=3)
    )

    event = updated.events[-1]
    assert event.event_type == "step_rolled_back"
    assert event.step_number == 1


def test_record_paused_adds_an_event_with_no_step():
    service = SalesTimelineService()
    timeline = service.create(_enrollment(), now=_T0)

    updated = service.record_paused(timeline, now=_T0 + timedelta(minutes=4))

    event = updated.events[-1]
    assert event.event_type == "paused"
    assert event.step_number is None
    assert event.step_name is None


def test_record_resumed_adds_an_event():
    service = SalesTimelineService()
    timeline = service.create(_enrollment(), now=_T0)

    updated = service.record_resumed(timeline, now=_T0 + timedelta(minutes=5))

    assert updated.events[-1].event_type == "resumed"


def test_record_finished_adds_an_event():
    service = SalesTimelineService()
    timeline = service.create(_enrollment(), now=_T0)

    updated = service.record_finished(timeline, now=_T0 + timedelta(minutes=6))

    assert updated.events[-1].event_type == "finished"


def test_ordem_cronologica_preservada_across_every_operation():
    service = SalesTimelineService()
    timeline = service.create(_enrollment(), now=_T0)

    timeline = service.record_started(timeline, step=_STEPS[0], now=_T0 + timedelta(minutes=1))
    timeline = service.record_step_completed(
        timeline, _STEPS[0], now=_T0 + timedelta(minutes=2)
    )
    timeline = service.record_paused(timeline, now=_T0 + timedelta(minutes=3))
    timeline = service.record_resumed(timeline, now=_T0 + timedelta(minutes=4))
    timeline = service.record_finished(timeline, now=_T0 + timedelta(minutes=5))

    occurred_at = [event.occurred_at for event in timeline.events]
    assert occurred_at == sorted(occurred_at)
    assert [event.event_type for event in timeline.events] == [
        "started",
        "step_completed",
        "paused",
        "resumed",
        "finished",
    ]


def test_imutabilidade_da_timeline_never_changes_the_previous_instance():
    service = SalesTimelineService()
    original = service.create(_enrollment(), now=_T0)

    updated = service.record_started(original, now=_T0 + timedelta(minutes=1))

    assert original.events == []
    assert len(updated.events) == 1
    assert original is not updated

    with pytest.raises(ValidationError):
        original.last_updated = _T0 + timedelta(hours=1)


def test_imutabilidade_dos_eventos_rejects_attribute_assignment():
    service = SalesTimelineService()
    timeline = service.create(_enrollment(), now=_T0)
    timeline = service.record_started(timeline, now=_T0 + timedelta(minutes=1))

    with pytest.raises(ValidationError):
        timeline.events[0].description = "Alterado."


def test_metadata_preservado_is_carried_through_unchanged():
    service = SalesTimelineService()
    timeline = service.create(_enrollment(), now=_T0)
    metadata = {"source": "unit-test", "channel": "whatsapp"}

    updated = service.record_started(timeline, now=_T0 + timedelta(minutes=1), metadata=metadata)

    assert updated.events[-1].metadata == metadata


def test_build_default_sales_timeline_service_returns_a_usable_service():
    service = build_default_sales_timeline_service()

    assert isinstance(service, SalesTimelineService)
    timeline = service.create(_enrollment(), now=_T0)
    updated = service.record_started(timeline, now=_T0 + timedelta(minutes=1))
    assert len(updated.events) == 1


def test_nenhuma_dependencia_de_runtime():
    source = inspect.getsource(sales_timeline_service)
    assert "Runtime" not in source


def test_nenhuma_dependencia_de_workflow():
    source = inspect.getsource(sales_timeline_service)
    assert "Workflow" not in source


def test_nenhuma_dependencia_de_crm_engine():
    source = inspect.getsource(sales_timeline_service)
    assert "CRMEngine" not in source
