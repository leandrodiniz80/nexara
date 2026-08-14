import inspect
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.crm.models.crm_opportunity import CRMOpportunity
from app.crm.services import sales_pipeline_intelligence_service
from app.crm.services.sales_benchmark_result import SalesBenchmarkResult
from app.crm.services.sales_cadence import SalesCadence
from app.crm.services.sales_cadence_execution_service import SalesCadenceExecutionService
from app.crm.services.sales_cadence_step import SalesCadenceStep
from app.crm.services.sales_coaching_result import SalesCoachingHealth, SalesCoachingResult
from app.crm.services.sales_enrollment import SalesEnrollment
from app.crm.services.sales_execution_analytics import SalesExecutionAnalytics
from app.crm.services.sales_execution_metrics import SalesExecutionMetrics
from app.crm.services.sales_pipeline_intelligence_service import (
    SalesPipelineIntelligenceService,
)
from app.crm.services.sales_pipeline_intelligence_service_factory import (
    build_default_sales_pipeline_intelligence_service,
)
from app.crm.services.sales_pipeline_summary import SalesPipelineSummary
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


def _benchmark() -> SalesBenchmarkResult:
    return SalesBenchmarkResult(
        average_completion_rate=50.0,
        average_duration=timedelta(minutes=10),
        best_completion_rate=100.0,
        worst_completion_rate=0.0,
        fastest_duration=timedelta(minutes=1),
        slowest_duration=timedelta(minutes=60),
        ranking_position=1,
        total_compared=1,
        above_average=False,
        generated_at=_T0,
    )


def _entry(
    *,
    completion_rate: float,
    health: SalesCoachingHealth,
    pause_count: int = 0,
    rollback_count: int = 0,
    finished: bool = False,
    duration_minutes: float | None = 10,
):
    opportunity = _opportunity()
    playbook = _playbook()
    cadence = _cadence()
    execution = SalesCadenceExecutionService().start(cadence, opportunity, now=_T0)
    enrollment = SalesEnrollment(
        opportunity=opportunity,
        playbook=playbook,
        cadence=cadence,
        execution=execution,
        started_at=execution.started_at,
        status=execution.status,
    )
    timeline = SalesTimelineService().create(enrollment, now=_T0)
    metrics = SalesExecutionMetrics(
        total_steps=cadence.total_steps,
        completed_steps=0,
        remaining_steps=len(execution.remaining_steps),
        completion_rate=completion_rate,
        total_events=0,
        pause_count=pause_count,
        resume_count=0,
        rollback_count=rollback_count,
        finished=finished,
        started_at=_T0,
        finished_at=_T0 if finished else None,
        total_duration=(
            timedelta(minutes=duration_minutes) if duration_minutes is not None else None
        ),
    )
    analytics = SalesExecutionAnalytics(
        enrollment=enrollment, timeline=timeline, metrics=metrics, generated_at=_T0
    )
    coaching = SalesCoachingResult(
        benchmark=_benchmark(), recommendations=[], overall_health=health, generated_at=_T0
    )
    return analytics, coaching


def test_pipeline_vazio_returns_zeroed_summary_with_no_insights():
    service = SalesPipelineIntelligenceService()

    summary = service.summarize([], now=_T0)

    assert summary.total_opportunities == 0
    assert summary.healthy == 0
    assert summary.attention == 0
    assert summary.critical == 0
    assert summary.average_completion_rate == 0.0
    assert summary.average_duration is None
    assert summary.total_pauses == 0
    assert summary.total_rollbacks == 0
    assert summary.total_finished == 0
    assert summary.insights == []
    assert summary.overall_health == SalesCoachingHealth.HEALTHY


def test_pipeline_saudavel_when_most_opportunities_are_healthy():
    entries = [
        _entry(completion_rate=90.0, health=SalesCoachingHealth.HEALTHY),
        _entry(completion_rate=85.0, health=SalesCoachingHealth.HEALTHY),
        _entry(completion_rate=80.0, health=SalesCoachingHealth.HEALTHY),
        _entry(completion_rate=50.0, health=SalesCoachingHealth.ATTENTION),
    ]
    service = SalesPipelineIntelligenceService()

    summary = service.summarize(entries, now=_T0)

    assert summary.healthy == 3
    assert summary.overall_health == SalesCoachingHealth.HEALTHY
    assert any(i.title == "Pipeline saudável" for i in summary.insights)


def test_pipeline_critico_when_most_opportunities_are_critical():
    entries = [
        _entry(completion_rate=10.0, health=SalesCoachingHealth.CRITICAL),
        _entry(completion_rate=15.0, health=SalesCoachingHealth.CRITICAL),
        _entry(completion_rate=20.0, health=SalesCoachingHealth.CRITICAL),
        _entry(completion_rate=90.0, health=SalesCoachingHealth.HEALTHY),
    ]
    service = SalesPipelineIntelligenceService()

    summary = service.summarize(entries, now=_T0)

    assert summary.critical == 3
    assert summary.overall_health == SalesCoachingHealth.CRITICAL
    assert any(i.title == "Pipeline em risco" for i in summary.insights)


def test_pipeline_atencao_when_neither_extreme_dominates():
    entries = [
        _entry(completion_rate=60.0, health=SalesCoachingHealth.ATTENTION),
        _entry(completion_rate=55.0, health=SalesCoachingHealth.ATTENTION),
        _entry(completion_rate=90.0, health=SalesCoachingHealth.HEALTHY),
        _entry(completion_rate=10.0, health=SalesCoachingHealth.CRITICAL),
    ]
    service = SalesPipelineIntelligenceService()

    summary = service.summarize(entries, now=_T0)

    assert summary.overall_health == SalesCoachingHealth.ATTENTION


def test_completion_medio_is_the_average_across_the_pipeline():
    entries = [
        _entry(completion_rate=100.0, health=SalesCoachingHealth.HEALTHY),
        _entry(completion_rate=0.0, health=SalesCoachingHealth.CRITICAL),
    ]
    service = SalesPipelineIntelligenceService()

    summary = service.summarize(entries, now=_T0)

    assert summary.average_completion_rate == 50.0


def test_duration_media_is_the_average_across_the_pipeline():
    entries = [
        _entry(completion_rate=50.0, health=SalesCoachingHealth.ATTENTION, duration_minutes=10),
        _entry(completion_rate=50.0, health=SalesCoachingHealth.ATTENTION, duration_minutes=30),
    ]
    service = SalesPipelineIntelligenceService()

    summary = service.summarize(entries, now=_T0)

    assert summary.average_duration == timedelta(minutes=20)


def test_total_pauses_sums_every_opportunitys_pause_count():
    entries = [
        _entry(completion_rate=50.0, health=SalesCoachingHealth.ATTENTION, pause_count=2),
        _entry(completion_rate=50.0, health=SalesCoachingHealth.ATTENTION, pause_count=3),
    ]
    service = SalesPipelineIntelligenceService()

    summary = service.summarize(entries, now=_T0)

    assert summary.total_pauses == 5


def test_total_rollbacks_sums_every_opportunitys_rollback_count():
    entries = [
        _entry(completion_rate=50.0, health=SalesCoachingHealth.ATTENTION, rollback_count=2),
        _entry(completion_rate=50.0, health=SalesCoachingHealth.ATTENTION, rollback_count=3),
    ]
    service = SalesPipelineIntelligenceService()

    summary = service.summarize(entries, now=_T0)

    assert summary.total_rollbacks == 5
    assert any(i.title == "Problemas de qualificação" for i in summary.insights)


def test_total_finished_counts_the_finished_opportunities():
    entries = [
        _entry(completion_rate=100.0, health=SalesCoachingHealth.HEALTHY, finished=True),
        _entry(completion_rate=50.0, health=SalesCoachingHealth.ATTENTION, finished=False),
    ]
    service = SalesPipelineIntelligenceService()

    summary = service.summarize(entries, now=_T0)

    assert summary.total_finished == 1


def test_baixa_evolucao_insight_when_average_completion_is_low():
    entries = [
        _entry(completion_rate=10.0, health=SalesCoachingHealth.CRITICAL),
        _entry(completion_rate=20.0, health=SalesCoachingHealth.CRITICAL),
    ]
    service = SalesPipelineIntelligenceService()

    summary = service.summarize(entries, now=_T0)

    assert any(i.title == "Baixa evolução comercial" for i in summary.insights)


def test_imutabilidade_rejects_attribute_assignment():
    entries = [_entry(completion_rate=90.0, health=SalesCoachingHealth.HEALTHY)]
    service = SalesPipelineIntelligenceService()

    summary = service.summarize(entries, now=_T0)

    with pytest.raises(ValidationError):
        summary.total_opportunities = 99

    if summary.insights:
        with pytest.raises(ValidationError):
            summary.insights[0].severity = "BAIXA"


def test_build_default_sales_pipeline_intelligence_service_returns_a_usable_service():
    service = build_default_sales_pipeline_intelligence_service()
    entries = [_entry(completion_rate=90.0, health=SalesCoachingHealth.HEALTHY)]

    assert isinstance(service, SalesPipelineIntelligenceService)
    summary = service.summarize(entries, now=_T0)
    assert isinstance(summary, SalesPipelineSummary)
    assert summary.total_opportunities == 1


def test_nenhuma_dependencia_de_runtime():
    source = inspect.getsource(sales_pipeline_intelligence_service)
    assert "Runtime" not in source


def test_nenhuma_dependencia_de_workflow():
    source = inspect.getsource(sales_pipeline_intelligence_service)
    assert "Workflow" not in source


def test_nenhuma_dependencia_de_crm_engine():
    source = inspect.getsource(sales_pipeline_intelligence_service)
    assert "CRMEngine" not in source
