from datetime import datetime, timedelta, timezone

from app.crm.services.sales_coaching_result import SalesCoachingHealth, SalesCoachingResult
from app.crm.services.sales_execution_analytics import SalesExecutionAnalytics
from app.crm.services.sales_pipeline_insight import SalesPipelineInsight
from app.crm.services.sales_pipeline_summary import SalesPipelineSummary

_CRITICAL_SHARE_THRESHOLD = 0.5
_HEALTHY_SHARE_THRESHOLD = 0.7
_LOW_AVERAGE_COMPLETION_RATE = 50.0
_HIGH_AVERAGE_ROLLBACKS = 1.0

PipelineEntry = tuple[SalesExecutionAnalytics, SalesCoachingResult]


class SalesPipelineIntelligenceService:
    """Aggregates many individually-coached opportunities into one
    consolidated view of the pipeline's commercial health — a pure,
    deterministic aggregation: no AI, no probabilistic inference, no fixed
    rule beyond simple counts/averages/thresholds. No persistence, no
    CRMEngine, no Runtime, no Workflow, no Automation, no Adapter, no Rule,
    no Decision. SalesCoachingService remains the only place that analyzes
    a single opportunity; this class only ever summarizes a population of
    its already-computed results.

    SalesCoachingResult alone does not carry the raw per-execution metrics
    (pause/rollback counts, completion rate, duration, finished) needed for
    the sums this sprint asks for — those live on SalesExecutionAnalytics,
    one level below SalesCoachingResult, and are not re-exposed by it. Each
    pipeline entry is therefore the pair of the two: the SalesCoachingResult
    supplies each opportunity's health tier, and its paired
    SalesExecutionAnalytics supplies the raw metrics to sum and average.
    This mirrors the same kind of deliberate, documented input-shape
    adjustment already used for SalesWorkQueueService in an earlier sprint.
    """

    def summarize(
        self,
        entries: list[PipelineEntry],
        *,
        now: datetime | None = None,
    ) -> SalesPipelineSummary:
        now = now or datetime.now(timezone.utc)
        total = len(entries)

        if total == 0:
            return SalesPipelineSummary(
                total_opportunities=0,
                healthy=0,
                attention=0,
                critical=0,
                average_completion_rate=0.0,
                average_duration=None,
                total_pauses=0,
                total_rollbacks=0,
                total_finished=0,
                overall_health=SalesCoachingHealth.HEALTHY,
                insights=[],
                generated_at=now,
            )

        healthy = self._count_health(entries, SalesCoachingHealth.HEALTHY)
        attention = self._count_health(entries, SalesCoachingHealth.ATTENTION)
        critical = self._count_health(entries, SalesCoachingHealth.CRITICAL)

        completion_rates = [analytics.metrics.completion_rate for analytics, _ in entries]
        durations = [
            analytics.metrics.total_duration
            for analytics, _ in entries
            if analytics.metrics.total_duration is not None
        ]
        total_pauses = sum(analytics.metrics.pause_count for analytics, _ in entries)
        total_rollbacks = sum(analytics.metrics.rollback_count for analytics, _ in entries)
        total_finished = sum(1 for analytics, _ in entries if analytics.metrics.finished)

        average_completion_rate = sum(completion_rates) / total
        average_duration = sum(durations, timedelta()) / len(durations) if durations else None

        critical_share = critical / total
        healthy_share = healthy / total
        average_rollbacks = total_rollbacks / total

        insights = self._insights(
            entries,
            total=total,
            critical=critical,
            healthy=healthy,
            critical_share=critical_share,
            healthy_share=healthy_share,
            average_completion_rate=average_completion_rate,
            average_rollbacks=average_rollbacks,
        )

        return SalesPipelineSummary(
            total_opportunities=total,
            healthy=healthy,
            attention=attention,
            critical=critical,
            average_completion_rate=average_completion_rate,
            average_duration=average_duration,
            total_pauses=total_pauses,
            total_rollbacks=total_rollbacks,
            total_finished=total_finished,
            overall_health=self._overall_health(critical_share, healthy_share),
            insights=insights,
            generated_at=now,
        )

    @staticmethod
    def _count_health(entries: list[PipelineEntry], health: SalesCoachingHealth) -> int:
        return sum(1 for _, coaching in entries if coaching.overall_health == health)

    @staticmethod
    def _overall_health(critical_share: float, healthy_share: float) -> SalesCoachingHealth:
        if critical_share > _CRITICAL_SHARE_THRESHOLD:
            return SalesCoachingHealth.CRITICAL
        if healthy_share > _HEALTHY_SHARE_THRESHOLD:
            return SalesCoachingHealth.HEALTHY
        return SalesCoachingHealth.ATTENTION

    @staticmethod
    def _insights(
        entries: list[PipelineEntry],
        *,
        total: int,
        critical: int,
        healthy: int,
        critical_share: float,
        healthy_share: float,
        average_completion_rate: float,
        average_rollbacks: float,
    ) -> list[SalesPipelineInsight]:
        insights: list[SalesPipelineInsight] = []

        if critical_share > _CRITICAL_SHARE_THRESHOLD:
            insights.append(
                SalesPipelineInsight(
                    title="Pipeline em risco",
                    description=(
                        f"{critical} de {total} oportunidades estão em estado crítico."
                    ),
                    severity="ALTA",
                    affected_opportunities=critical,
                )
            )

        if average_completion_rate < _LOW_AVERAGE_COMPLETION_RATE:
            insights.append(
                SalesPipelineInsight(
                    title="Baixa evolução comercial",
                    description=(
                        "A taxa média de conclusão do pipeline está abaixo do esperado."
                    ),
                    severity="ALTA",
                    affected_opportunities=total,
                )
            )

        if average_rollbacks > _HIGH_AVERAGE_ROLLBACKS:
            rollback_affected = sum(
                1 for analytics, _ in entries if analytics.metrics.rollback_count > 0
            )
            insights.append(
                SalesPipelineInsight(
                    title="Problemas de qualificação",
                    description="O número médio de retornos de etapa está elevado.",
                    severity="MÉDIA",
                    affected_opportunities=rollback_affected,
                )
            )

        if healthy_share > _HEALTHY_SHARE_THRESHOLD:
            insights.append(
                SalesPipelineInsight(
                    title="Pipeline saudável",
                    description=f"{healthy} de {total} oportunidades estão saudáveis.",
                    severity="BAIXA",
                    affected_opportunities=healthy,
                )
            )

        return insights
