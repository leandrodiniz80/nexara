import inspect
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.crm.models.crm_opportunity import CRMOpportunity
from app.crm.services import sales_coaching_service
from app.crm.services.sales_benchmark_result import SalesBenchmarkResult
from app.crm.services.sales_cadence import SalesCadence
from app.crm.services.sales_cadence_execution_service import SalesCadenceExecutionService
from app.crm.services.sales_cadence_step import SalesCadenceStep
from app.crm.services.sales_coaching_result import SalesCoachingHealth, SalesCoachingResult
from app.crm.services.sales_coaching_service import SalesCoachingService
from app.crm.services.sales_coaching_service_factory import build_default_sales_coaching_service
from app.crm.services.sales_enrollment import SalesEnrollment
from app.crm.services.sales_execution_analytics import SalesExecutionAnalytics
from app.crm.services.sales_execution_metrics import SalesExecutionMetrics
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


def _analytics(
    *,
    completion_rate: float = 50.0,
    pause_count: int = 0,
    rollback_count: int = 0,
    duration_minutes: float | None = 10,
) -> SalesExecutionAnalytics:
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
        finished=False,
        started_at=_T0,
        finished_at=None,
        total_duration=(
            timedelta(minutes=duration_minutes) if duration_minutes is not None else None
        ),
    )
    return SalesExecutionAnalytics(
        enrollment=enrollment, timeline=timeline, metrics=metrics, generated_at=_T0
    )


def _benchmark(
    *,
    average_completion_rate: float = 50.0,
    average_duration_minutes: float | None = 10,
    above_average: bool = False,
) -> SalesBenchmarkResult:
    return SalesBenchmarkResult(
        average_completion_rate=average_completion_rate,
        average_duration=(
            timedelta(minutes=average_duration_minutes)
            if average_duration_minutes is not None
            else None
        ),
        best_completion_rate=100.0,
        worst_completion_rate=0.0,
        fastest_duration=timedelta(minutes=1),
        slowest_duration=timedelta(minutes=60),
        ranking_position=1,
        total_compared=1,
        above_average=above_average,
        generated_at=_T0,
    )


def test_completion_baixo_recommends_revisiting_the_approach():
    analytics = _analytics(completion_rate=30.0)
    benchmark = _benchmark(average_completion_rate=50.0)
    service = SalesCoachingService()

    result = service.coach(analytics, benchmark, now=_T0)

    titles = [r.title for r in result.recommendations]
    assert "Revisar abordagem comercial" in titles


def test_completion_alto_recommends_an_efficient_strategy():
    analytics = _analytics(completion_rate=90.0)
    benchmark = _benchmark(average_completion_rate=50.0, above_average=True)
    service = SalesCoachingService()

    result = service.coach(analytics, benchmark, now=_T0)

    titles = [r.title for r in result.recommendations]
    assert "Estratégia eficiente" in titles


def test_pause_elevado_recommends_reducing_contact_intervals():
    analytics = _analytics(completion_rate=60.0, pause_count=4)
    benchmark = _benchmark()
    service = SalesCoachingService()

    result = service.coach(analytics, benchmark, now=_T0)

    titles = [r.title for r in result.recommendations]
    assert "Reduzir tempo entre contatos" in titles


def test_rollback_elevado_recommends_reassessing_qualification():
    analytics = _analytics(completion_rate=60.0, rollback_count=3)
    benchmark = _benchmark()
    service = SalesCoachingService()

    result = service.coach(analytics, benchmark, now=_T0)

    titles = [r.title for r in result.recommendations]
    assert "Reavaliar qualificação" in titles


def test_duration_elevada_recommends_a_faster_cadence():
    analytics = _analytics(completion_rate=60.0, duration_minutes=60)
    benchmark = _benchmark(average_duration_minutes=10)
    service = SalesCoachingService()

    result = service.coach(analytics, benchmark, now=_T0)

    titles = [r.title for r in result.recommendations]
    assert "Cadência muito lenta" in titles


def test_sem_recomendacoes_when_nothing_crosses_a_threshold():
    analytics = _analytics(completion_rate=50.0, duration_minutes=10)
    benchmark = _benchmark(average_completion_rate=50.0, average_duration_minutes=10)
    service = SalesCoachingService()

    result = service.coach(analytics, benchmark, now=_T0)

    assert result.recommendations == []


def test_overall_health_healthy_when_metrics_are_all_good():
    analytics = _analytics(completion_rate=80.0, pause_count=0, rollback_count=0)
    benchmark = _benchmark()
    service = SalesCoachingService()

    result = service.coach(analytics, benchmark, now=_T0)

    assert result.overall_health == SalesCoachingHealth.HEALTHY


def test_overall_health_attention_for_a_mid_range_completion_rate():
    analytics = _analytics(completion_rate=50.0, pause_count=0, rollback_count=0)
    benchmark = _benchmark()
    service = SalesCoachingService()

    result = service.coach(analytics, benchmark, now=_T0)

    assert result.overall_health == SalesCoachingHealth.ATTENTION


def test_overall_health_critical_for_a_low_completion_rate():
    analytics = _analytics(completion_rate=20.0)
    benchmark = _benchmark()
    service = SalesCoachingService()

    result = service.coach(analytics, benchmark, now=_T0)

    assert result.overall_health == SalesCoachingHealth.CRITICAL


def test_metadata_preservado_across_every_recommendation():
    analytics = _analytics(completion_rate=30.0, pause_count=4, rollback_count=3)
    benchmark = _benchmark()
    service = SalesCoachingService()
    metadata = {"source": "unit-test"}

    result = service.coach(analytics, benchmark, now=_T0, metadata=metadata)

    assert len(result.recommendations) >= 2
    for recommendation in result.recommendations:
        assert recommendation.metadata == metadata


def test_imutabilidade_rejects_attribute_assignment():
    analytics = _analytics(completion_rate=30.0)
    benchmark = _benchmark()
    service = SalesCoachingService()

    result = service.coach(analytics, benchmark, now=_T0)

    with pytest.raises(ValidationError):
        result.overall_health = SalesCoachingHealth.HEALTHY

    with pytest.raises(ValidationError):
        result.recommendations[0].priority = "BAIXA"


def test_build_default_sales_coaching_service_returns_a_usable_service():
    service = build_default_sales_coaching_service()
    analytics = _analytics(completion_rate=30.0)
    benchmark = _benchmark()

    assert isinstance(service, SalesCoachingService)
    result = service.coach(analytics, benchmark, now=_T0)
    assert isinstance(result, SalesCoachingResult)


def test_nenhuma_dependencia_de_runtime():
    source = inspect.getsource(sales_coaching_service)
    assert "Runtime" not in source


def test_nenhuma_dependencia_de_workflow():
    source = inspect.getsource(sales_coaching_service)
    assert "Workflow" not in source


def test_nenhuma_dependencia_de_crm_engine():
    source = inspect.getsource(sales_coaching_service)
    assert "CRMEngine" not in source
