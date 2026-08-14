from datetime import datetime, timezone
from typing import Any

from app.crm.services.sales_benchmark_result import SalesBenchmarkResult
from app.crm.services.sales_coaching_recommendation import SalesCoachingRecommendation
from app.crm.services.sales_coaching_result import SalesCoachingHealth, SalesCoachingResult
from app.crm.services.sales_execution_analytics import SalesExecutionAnalytics
from app.crm.services.sales_execution_metrics import SalesExecutionMetrics

_LOW_COMPLETION_RATE = 40.0
_ATTENTION_COMPLETION_RATE = 70.0
_HIGH_PAUSE_COUNT = 3
_HIGH_ROLLBACK_COUNT = 2


class SalesCoachingService:
    """Turns SalesExecutionMetrics and a SalesBenchmarkResult into
    deterministic operational recommendations — a fixed set of threshold
    checks, not AI, not a Decision Strategy, not a Business Rule. No
    persistence, no CRMEngine, no Runtime, no Workflow, no Automation, no
    Adapter: it only ever reads the SalesExecutionAnalytics/
    SalesBenchmarkResult its caller already has.

    SalesExecutionAnalyticsService remains the only place that computes an
    execution's own metrics, and SalesBenchmarkService remains the only
    place that compares executions statistically; this class only ever
    turns their already-computed output into coaching advice.
    """

    def coach(
        self,
        analytics: SalesExecutionAnalytics,
        benchmark: SalesBenchmarkResult,
        *,
        now: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SalesCoachingResult:
        now = now or datetime.now(timezone.utc)
        metrics = analytics.metrics
        shared_metadata = dict(metadata or {})

        recommendations: list[SalesCoachingRecommendation] = []

        if metrics.completion_rate < _LOW_COMPLETION_RATE:
            recommendations.append(
                SalesCoachingRecommendation(
                    title="Revisar abordagem comercial",
                    description=(
                        "A taxa de conclusão está abaixo de "
                        f"{_LOW_COMPLETION_RATE:.0f}%; reavalie a abordagem utilizada."
                    ),
                    priority="ALTA",
                    category="abordagem",
                    confidence=0.9,
                    metadata=shared_metadata,
                )
            )

        if metrics.pause_count > _HIGH_PAUSE_COUNT:
            recommendations.append(
                SalesCoachingRecommendation(
                    title="Reduzir tempo entre contatos",
                    description=(
                        f"A cadência foi pausada {metrics.pause_count} vezes; "
                        "reduza o intervalo entre contatos."
                    ),
                    priority="MÉDIA",
                    category="cadência",
                    confidence=0.8,
                    metadata=shared_metadata,
                )
            )

        if metrics.rollback_count > _HIGH_ROLLBACK_COUNT:
            recommendations.append(
                SalesCoachingRecommendation(
                    title="Reavaliar qualificação",
                    description=(
                        f"Houve {metrics.rollback_count} retornos de etapa; "
                        "reavalie a qualificação da oportunidade."
                    ),
                    priority="ALTA",
                    category="qualificação",
                    confidence=0.85,
                    metadata=shared_metadata,
                )
            )

        if (
            metrics.total_duration is not None
            and benchmark.average_duration is not None
            and metrics.total_duration > benchmark.average_duration
        ):
            recommendations.append(
                SalesCoachingRecommendation(
                    title="Cadência muito lenta",
                    description="A duração está acima da média do grupo comparado.",
                    priority="MÉDIA",
                    category="cadência",
                    confidence=0.75,
                    metadata=shared_metadata,
                )
            )

        if benchmark.above_average:
            recommendations.append(
                SalesCoachingRecommendation(
                    title="Estratégia eficiente",
                    description="A taxa de conclusão está acima da média do grupo comparado.",
                    priority="BAIXA",
                    category="estratégia",
                    confidence=0.7,
                    metadata=shared_metadata,
                )
            )

        return SalesCoachingResult(
            benchmark=benchmark,
            recommendations=recommendations,
            overall_health=self._overall_health(metrics.completion_rate, metrics),
            generated_at=now,
        )

    @staticmethod
    def _overall_health(
        completion_rate: float, metrics: SalesExecutionMetrics
    ) -> SalesCoachingHealth:
        if (
            completion_rate < _LOW_COMPLETION_RATE
            or metrics.rollback_count > _HIGH_ROLLBACK_COUNT
        ):
            return SalesCoachingHealth.CRITICAL
        if (
            completion_rate < _ATTENTION_COMPLETION_RATE
            or metrics.pause_count > _HIGH_PAUSE_COUNT
        ):
            return SalesCoachingHealth.ATTENTION
        return SalesCoachingHealth.HEALTHY
