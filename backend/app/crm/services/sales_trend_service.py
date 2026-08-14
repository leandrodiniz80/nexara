from datetime import datetime, timezone

from app.crm.services.sales_trend import SalesTrend, SalesTrendDirection
from app.crm.services.sales_trend_snapshot import SalesTrendSnapshot


class SalesTrendService:
    """Compares two SalesTrendSnapshots taken at different points in time
    and determines the resulting trend — a pure, deterministic comparison:
    no AI, no Machine Learning, no regression. No persistence, no
    CRMEngine, no Runtime, no Workflow, no Automation, no Adapter, no Rule,
    no Decision. SalesForecastService remains the only place that predicts
    revenue, SalesTargetService remains the only place that compares
    against a goal, and SalesPipelineIntelligenceService remains the only
    place that measures operational health; this class only ever compares
    two already-taken snapshots of their output over time.
    """

    def compare(
        self,
        previous: SalesTrendSnapshot,
        current: SalesTrendSnapshot,
        *,
        now: datetime | None = None,
    ) -> SalesTrend:
        now = now or datetime.now(timezone.utc)

        revenue_delta = current.expected_revenue - previous.expected_revenue
        completion_delta = current.completion_rate - previous.completion_rate
        progress_delta = current.overall_progress - previous.overall_progress
        health_delta = current.healthy - previous.healthy

        return SalesTrend(
            trend_direction=self._trend_direction(revenue_delta, progress_delta),
            revenue_delta=revenue_delta,
            completion_delta=completion_delta,
            progress_delta=progress_delta,
            health_delta=health_delta,
            is_improving=(
                revenue_delta >= 0 and completion_delta >= 0 and progress_delta >= 0
            ),
            generated_at=now,
        )

    @staticmethod
    def _trend_direction(revenue_delta: float, progress_delta: float) -> SalesTrendDirection:
        if revenue_delta > 0 and progress_delta >= 0:
            return SalesTrendDirection.UP
        if revenue_delta < 0:
            return SalesTrendDirection.DOWN
        return SalesTrendDirection.STABLE
