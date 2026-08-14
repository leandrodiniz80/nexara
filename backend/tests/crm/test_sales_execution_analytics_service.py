import inspect
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.crm.models.crm_opportunity import CRMOpportunity
from app.crm.services import sales_execution_analytics_service
from app.crm.services.sales_cadence import SalesCadence
from app.crm.services.sales_cadence_execution_service import SalesCadenceExecutionService
from app.crm.services.sales_cadence_step import SalesCadenceStep
from app.crm.services.sales_enrollment_service import SalesEnrollmentService
from app.crm.services.sales_execution_analytics import SalesExecutionAnalytics
from app.crm.services.sales_execution_analytics_service import SalesExecutionAnalyticsService
from app.crm.services.sales_execution_analytics_service_factory import (
    build_default_sales_execution_analytics_service,
)
from app.crm.services.sales_playbook import SalesPlaybook
from app.crm.services.sales_timeline_service import SalesTimelineService

_T0 = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)

_STEPS = [
    SalesCadenceStep(
        step_number=1, action="Primeiro e-mail", recommended_delay=0, channel="E-mail", goal="g1"
    ),
    SalesCadenceStep(
        step_number=2, action="WhatsApp", recommended_delay=2, channel="WhatsApp", goal="g2"
    ),
    SalesCadenceStep(
        step_number=3, action="Ligação", recommended_delay=5, channel="Telefone", goal="g3"
    ),
    SalesCadenceStep(
        step_number=4, action="Segundo e-mail", recommended_delay=8, channel="E-mail", goal="g4"
    ),
    SalesCadenceStep(
        step_number=5, action="Follow-up final", recommended_delay=12, channel="E-mail", goal="g5"
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
        recommended_channels=["E-mail", "WhatsApp", "Telefone"],
    )


def _cadence() -> SalesCadence:
    return SalesCadence(
        steps=list(_STEPS), total_steps=len(_STEPS), current_step=_STEPS[0], next_step=_STEPS[1]
    )


def _enrollment(execution_service: SalesCadenceExecutionService):
    enrollment_service = SalesEnrollmentService(execution_service)
    return enrollment_service.enroll(_opportunity(), _playbook(), _cadence(), now=_T0)


def test_timeline_vazia_produces_zeroed_history_metrics():
    execution_service = SalesCadenceExecutionService()
    enrollment = _enrollment(execution_service)
    timeline = SalesTimelineService().create(enrollment, now=_T0)
    service = SalesExecutionAnalyticsService()

    analytics = service.analyze(enrollment, timeline, now=_T0)

    assert analytics.metrics.total_events == 0
    assert analytics.metrics.pause_count == 0
    assert analytics.metrics.resume_count == 0
    assert analytics.metrics.rollback_count == 0
    assert analytics.metrics.finished is False
    assert analytics.metrics.started_at is None
    assert analytics.metrics.finished_at is None
    assert analytics.metrics.total_duration is None


def test_timeline_iniciada_records_started_at_and_an_open_duration():
    execution_service = SalesCadenceExecutionService()
    enrollment = _enrollment(execution_service)
    timeline_service = SalesTimelineService()
    timeline = timeline_service.create(enrollment, now=_T0)
    timeline = timeline_service.record_started(
        timeline, step=_STEPS[0], now=_T0 + timedelta(minutes=1)
    )
    service = SalesExecutionAnalyticsService()

    analytics = service.analyze(enrollment, timeline, now=_T0 + timedelta(minutes=5))

    assert analytics.metrics.started_at == _T0 + timedelta(minutes=1)
    assert analytics.metrics.finished is False
    assert analytics.metrics.finished_at is None
    assert analytics.metrics.total_duration == timedelta(minutes=4)


def test_timeline_concluida_computes_duration_from_started_to_finished():
    execution_service = SalesCadenceExecutionService()
    enrollment = _enrollment(execution_service)
    timeline_service = SalesTimelineService()
    timeline = timeline_service.create(enrollment, now=_T0)
    timeline = timeline_service.record_started(
        timeline, step=_STEPS[0], now=_T0 + timedelta(minutes=1)
    )
    timeline = timeline_service.record_finished(timeline, now=_T0 + timedelta(minutes=30))
    service = SalesExecutionAnalyticsService()

    analytics = service.analyze(enrollment, timeline, now=_T0 + timedelta(hours=2))

    assert analytics.metrics.finished is True
    assert analytics.metrics.finished_at == _T0 + timedelta(minutes=30)
    assert analytics.metrics.total_duration == timedelta(minutes=29)


def test_completion_rate_matches_the_execution_progress():
    execution_service = SalesCadenceExecutionService()
    enrollment = _enrollment(execution_service)
    execution_service.advance(enrollment.execution, now=_T0)
    execution_service.advance(enrollment.execution, now=_T0)
    timeline = SalesTimelineService().create(enrollment, now=_T0)
    service = SalesExecutionAnalyticsService()

    analytics = service.analyze(enrollment, timeline, now=_T0)

    assert analytics.metrics.completion_rate == 40.0
    assert 0.0 <= analytics.metrics.completion_rate <= 100.0


def test_rollback_count_reflects_only_the_timeline():
    execution_service = SalesCadenceExecutionService()
    enrollment = _enrollment(execution_service)
    timeline_service = SalesTimelineService()
    timeline = timeline_service.create(enrollment, now=_T0)
    timeline = timeline_service.record_step_rolled_back(timeline, _STEPS[0], now=_T0)
    timeline = timeline_service.record_step_rolled_back(timeline, _STEPS[1], now=_T0)
    service = SalesExecutionAnalyticsService()

    analytics = service.analyze(enrollment, timeline, now=_T0)

    assert analytics.metrics.rollback_count == 2


def test_pause_count_reflects_only_the_timeline():
    execution_service = SalesCadenceExecutionService()
    enrollment = _enrollment(execution_service)
    timeline_service = SalesTimelineService()
    timeline = timeline_service.create(enrollment, now=_T0)
    timeline = timeline_service.record_paused(timeline, now=_T0)
    timeline = timeline_service.record_paused(timeline, now=_T0)
    timeline = timeline_service.record_paused(timeline, now=_T0)
    service = SalesExecutionAnalyticsService()

    analytics = service.analyze(enrollment, timeline, now=_T0)

    assert analytics.metrics.pause_count == 3


def test_resume_count_reflects_only_the_timeline():
    execution_service = SalesCadenceExecutionService()
    enrollment = _enrollment(execution_service)
    timeline_service = SalesTimelineService()
    timeline = timeline_service.create(enrollment, now=_T0)
    timeline = timeline_service.record_resumed(timeline, now=_T0)
    service = SalesExecutionAnalyticsService()

    analytics = service.analyze(enrollment, timeline, now=_T0)

    assert analytics.metrics.resume_count == 1


def test_remaining_steps_derived_from_the_cadence_execution():
    execution_service = SalesCadenceExecutionService()
    enrollment = _enrollment(execution_service)
    timeline = SalesTimelineService().create(enrollment, now=_T0)
    service = SalesExecutionAnalyticsService()

    before = service.analyze(enrollment, timeline, now=_T0)
    execution_service.advance(enrollment.execution, now=_T0)
    after = service.analyze(enrollment, timeline, now=_T0)

    assert before.metrics.remaining_steps == 4
    assert after.metrics.remaining_steps == 3


def test_finished_is_true_even_after_a_rollback_recorded_later():
    execution_service = SalesCadenceExecutionService()
    enrollment = _enrollment(execution_service)
    timeline_service = SalesTimelineService()
    timeline = timeline_service.create(enrollment, now=_T0)
    timeline = timeline_service.record_finished(timeline, now=_T0 + timedelta(minutes=10))
    timeline = timeline_service.record_step_rolled_back(
        timeline, _STEPS[0], now=_T0 + timedelta(minutes=11)
    )
    service = SalesExecutionAnalyticsService()

    analytics = service.analyze(enrollment, timeline, now=_T0 + timedelta(minutes=20))

    assert analytics.metrics.finished is True
    assert analytics.metrics.rollback_count == 1


def test_total_duration_uses_now_when_not_yet_finished():
    execution_service = SalesCadenceExecutionService()
    enrollment = _enrollment(execution_service)
    timeline_service = SalesTimelineService()
    timeline = timeline_service.create(enrollment, now=_T0)
    timeline = timeline_service.record_started(timeline, now=_T0)
    service = SalesExecutionAnalyticsService()

    analytics = service.analyze(enrollment, timeline, now=_T0 + timedelta(hours=3))

    assert analytics.metrics.total_duration == timedelta(hours=3)


def test_analytics_imutavel_rejects_attribute_assignment():
    execution_service = SalesCadenceExecutionService()
    enrollment = _enrollment(execution_service)
    timeline = SalesTimelineService().create(enrollment, now=_T0)
    service = SalesExecutionAnalyticsService()

    analytics = service.analyze(enrollment, timeline, now=_T0)

    with pytest.raises(ValidationError):
        analytics.generated_at = _T0 + timedelta(days=1)

    with pytest.raises(ValidationError):
        analytics.metrics.finished = True


def test_build_default_sales_execution_analytics_service_returns_a_usable_service():
    service = build_default_sales_execution_analytics_service()
    execution_service = SalesCadenceExecutionService()
    enrollment = _enrollment(execution_service)
    timeline = SalesTimelineService().create(enrollment, now=_T0)

    assert isinstance(service, SalesExecutionAnalyticsService)
    analytics = service.analyze(enrollment, timeline, now=_T0)
    assert isinstance(analytics, SalesExecutionAnalytics)
    assert analytics.metrics.total_steps == 5


def test_nenhuma_dependencia_de_runtime():
    source = inspect.getsource(sales_execution_analytics_service)
    assert "Runtime" not in source


def test_nenhuma_dependencia_de_workflow():
    source = inspect.getsource(sales_execution_analytics_service)
    assert "Workflow" not in source


def test_nenhuma_dependencia_de_crm_engine():
    source = inspect.getsource(sales_execution_analytics_service)
    assert "CRMEngine" not in source
