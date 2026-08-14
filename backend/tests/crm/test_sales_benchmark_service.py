import inspect
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.crm.models.crm_opportunity import CRMOpportunity
from app.crm.services import sales_benchmark_service
from app.crm.services.sales_benchmark import SalesBenchmark
from app.crm.services.sales_benchmark_result import SalesBenchmarkResult
from app.crm.services.sales_benchmark_service import SalesBenchmarkService
from app.crm.services.sales_benchmark_service_factory import build_default_sales_benchmark_service
from app.crm.services.sales_cadence import SalesCadence
from app.crm.services.sales_cadence_execution_service import SalesCadenceExecutionService
from app.crm.services.sales_cadence_step import SalesCadenceStep
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
    completion_rate: float, duration_minutes: float | None
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
        pause_count=0,
        resume_count=0,
        rollback_count=0,
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


def test_benchmark_com_uma_execucao():
    solo = _analytics(50.0, 30)
    service = SalesBenchmarkService()

    result = service.compare(SalesBenchmark(analytics=solo, benchmark_group=[solo]), now=_T0)

    assert result.total_compared == 1
    assert result.ranking_position == 1
    assert result.average_completion_rate == 50.0
    assert result.above_average is False


def test_benchmark_com_multiplas_execucoes():
    a = _analytics(80.0, 10)
    b = _analytics(60.0, 20)
    c = _analytics(40.0, 30)
    service = SalesBenchmarkService()

    result = service.compare(SalesBenchmark(analytics=a, benchmark_group=[a, b, c]), now=_T0)

    assert result.total_compared == 3
    assert result.average_completion_rate == 60.0


def test_ranking_orders_by_completion_rate_desc_then_duration_asc():
    best = _analytics(90.0, 10)
    middle = _analytics(70.0, 5)
    worst = _analytics(50.0, 3)
    group = [best, middle, worst]
    service = SalesBenchmarkService()

    result_best = service.compare(SalesBenchmark(analytics=best, benchmark_group=group), now=_T0)
    result_middle = service.compare(
        SalesBenchmark(analytics=middle, benchmark_group=group), now=_T0
    )
    result_worst = service.compare(
        SalesBenchmark(analytics=worst, benchmark_group=group), now=_T0
    )

    assert result_best.ranking_position == 1
    assert result_middle.ranking_position == 2
    assert result_worst.ranking_position == 3


def test_ranking_breaks_ties_on_completion_rate_by_faster_duration():
    faster = _analytics(70.0, 5)
    slower = _analytics(70.0, 15)
    group = [faster, slower]
    service = SalesBenchmarkService()

    result_faster = service.compare(
        SalesBenchmark(analytics=faster, benchmark_group=group), now=_T0
    )
    result_slower = service.compare(
        SalesBenchmark(analytics=slower, benchmark_group=group), now=_T0
    )

    assert result_faster.ranking_position == 1
    assert result_slower.ranking_position == 2


def test_completion_rate_medio_is_the_average_across_the_group():
    a = _analytics(100.0, 10)
    b = _analytics(0.0, 10)
    service = SalesBenchmarkService()

    result = service.compare(SalesBenchmark(analytics=a, benchmark_group=[a, b]), now=_T0)

    assert result.average_completion_rate == 50.0


def test_duration_media_is_the_average_across_the_group():
    a = _analytics(50.0, 10)
    b = _analytics(50.0, 30)
    service = SalesBenchmarkService()

    result = service.compare(SalesBenchmark(analytics=a, benchmark_group=[a, b]), now=_T0)

    assert result.average_duration == timedelta(minutes=20)


def test_best_completion_rate_is_the_highest_in_the_group():
    a = _analytics(30.0, 10)
    b = _analytics(90.0, 10)
    c = _analytics(60.0, 10)
    service = SalesBenchmarkService()

    result = service.compare(SalesBenchmark(analytics=a, benchmark_group=[a, b, c]), now=_T0)

    assert result.best_completion_rate == 90.0


def test_worst_completion_rate_is_the_lowest_in_the_group():
    a = _analytics(30.0, 10)
    b = _analytics(90.0, 10)
    c = _analytics(60.0, 10)
    service = SalesBenchmarkService()

    result = service.compare(SalesBenchmark(analytics=a, benchmark_group=[a, b, c]), now=_T0)

    assert result.worst_completion_rate == 30.0


def test_fastest_duration_is_the_smallest_in_the_group():
    a = _analytics(50.0, 45)
    b = _analytics(50.0, 5)
    c = _analytics(50.0, 20)
    service = SalesBenchmarkService()

    result = service.compare(SalesBenchmark(analytics=a, benchmark_group=[a, b, c]), now=_T0)

    assert result.fastest_duration == timedelta(minutes=5)


def test_slowest_duration_is_the_largest_in_the_group():
    a = _analytics(50.0, 45)
    b = _analytics(50.0, 5)
    c = _analytics(50.0, 20)
    service = SalesBenchmarkService()

    result = service.compare(SalesBenchmark(analytics=a, benchmark_group=[a, b, c]), now=_T0)

    assert result.slowest_duration == timedelta(minutes=45)


def test_above_average_true_when_the_current_execution_beats_the_group():
    strong = _analytics(90.0, 10)
    weak = _analytics(10.0, 10)
    service = SalesBenchmarkService()

    result = service.compare(
        SalesBenchmark(analytics=strong, benchmark_group=[strong, weak]), now=_T0
    )

    assert result.above_average is True


def test_above_average_false_when_the_current_execution_trails_the_group():
    strong = _analytics(90.0, 10)
    weak = _analytics(10.0, 10)
    service = SalesBenchmarkService()

    result = service.compare(
        SalesBenchmark(analytics=weak, benchmark_group=[strong, weak]), now=_T0
    )

    assert result.above_average is False


def test_analytics_imutavel_rejects_attribute_assignment():
    solo = _analytics(50.0, 10)
    service = SalesBenchmarkService()
    benchmark = SalesBenchmark(analytics=solo, benchmark_group=[solo])

    result = service.compare(benchmark, now=_T0)

    with pytest.raises(ValidationError):
        result.above_average = True

    with pytest.raises(ValidationError):
        benchmark.analytics = _analytics(10.0, 10)


def test_build_default_sales_benchmark_service_returns_a_usable_service():
    service = build_default_sales_benchmark_service()
    solo = _analytics(50.0, 10)

    assert isinstance(service, SalesBenchmarkService)
    result = service.compare(SalesBenchmark(analytics=solo, benchmark_group=[solo]), now=_T0)
    assert isinstance(result, SalesBenchmarkResult)
    assert result.total_compared == 1


def test_nenhuma_dependencia_de_runtime():
    source = inspect.getsource(sales_benchmark_service)
    assert "Runtime" not in source


def test_nenhuma_dependencia_de_workflow():
    source = inspect.getsource(sales_benchmark_service)
    assert "Workflow" not in source


def test_nenhuma_dependencia_de_crm_engine():
    source = inspect.getsource(sales_benchmark_service)
    assert "CRMEngine" not in source
