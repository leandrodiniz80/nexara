from datetime import datetime, timedelta, timezone

from app.crm.services.sales_benchmark import SalesBenchmark
from app.crm.services.sales_benchmark_result import SalesBenchmarkResult
from app.crm.services.sales_execution_analytics import SalesExecutionAnalytics

_WORST_DURATION_RANK = timedelta.max


class SalesBenchmarkService:
    """Compares one SalesExecutionAnalytics against a population of others —
    nothing about how any of them were measured. A pure, deterministic
    calculation over values its caller already has: no persistence, no
    CRMEngine, no Runtime, no Workflow, no Automation, no AI, no Rule, no
    Decision, no Adapter. SalesExecutionAnalyticsService remains the only
    place that computes an individual execution's own metrics; this class
    only ever ranks and averages metrics that already exist.
    """

    def compare(
        self,
        benchmark: SalesBenchmark,
        *,
        now: datetime | None = None,
    ) -> SalesBenchmarkResult:
        now = now or datetime.now(timezone.utc)
        population = self._population(benchmark)

        completion_rates = [item.metrics.completion_rate for item in population]
        durations = [
            item.metrics.total_duration
            for item in population
            if item.metrics.total_duration is not None
        ]

        average_completion_rate = sum(completion_rates) / len(completion_rates)
        average_duration = sum(durations, timedelta()) / len(durations) if durations else None

        ranking_position = self._ranking_position(population, benchmark.analytics)

        return SalesBenchmarkResult(
            average_completion_rate=average_completion_rate,
            average_duration=average_duration,
            best_completion_rate=max(completion_rates),
            worst_completion_rate=min(completion_rates),
            fastest_duration=min(durations) if durations else None,
            slowest_duration=max(durations) if durations else None,
            ranking_position=ranking_position,
            total_compared=len(population),
            above_average=(
                benchmark.analytics.metrics.completion_rate > average_completion_rate
            ),
            generated_at=now,
        )

    @staticmethod
    def _population(benchmark: SalesBenchmark) -> list[SalesExecutionAnalytics]:
        population = list(benchmark.benchmark_group)
        if not any(item is benchmark.analytics for item in population):
            population.append(benchmark.analytics)
        return population

    @staticmethod
    def _ranking_position(
        population: list[SalesExecutionAnalytics], analytics: SalesExecutionAnalytics
    ) -> int:
        ranked = sorted(
            population,
            key=lambda item: (
                -item.metrics.completion_rate,
                item.metrics.total_duration
                if item.metrics.total_duration is not None
                else _WORST_DURATION_RANK,
            ),
        )
        for position, item in enumerate(ranked, start=1):
            if item is analytics:
                return position
        return len(ranked)
