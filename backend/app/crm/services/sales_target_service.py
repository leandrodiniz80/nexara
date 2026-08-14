from datetime import datetime, timezone

from app.crm.services.sales_forecast import SalesForecast
from app.crm.services.sales_pipeline_summary import SalesPipelineSummary
from app.crm.services.sales_target import SalesTarget
from app.crm.services.sales_target_progress import SalesTargetProgress

_CONVERSION_RATE_SCALE = 100.0


class SalesTargetService:
    """Compares a SalesForecast/SalesPipelineSummary against a SalesTarget —
    nothing about how either was computed. A pure, deterministic
    calculation: no AI, no Decision, no Rule, no Runtime, no Workflow, no
    Automation, no persistence, no Adapter, no CRMEngine.

    SalesForecastService remains the only place that predicts revenue, and
    SalesPipelineIntelligenceService remains the only place that measures
    operational health; this class only ever measures their already-
    computed output against a goal.

    `SalesPipelineSummary.average_completion_rate` is expressed on the
    platform's usual 0..100 scale, but every progress figure here is a 0..1
    fraction (per this sprint's own rule), so it is divided by 100 before
    being compared against `SalesTarget.target_conversion_rate` — itself
    already a 0..1 fraction.
    """

    def evaluate(
        self,
        target: SalesTarget,
        forecast: SalesForecast,
        pipeline_summary: SalesPipelineSummary,
        *,
        now: datetime | None = None,
    ) -> SalesTargetProgress:
        now = now or datetime.now(timezone.utc)

        current_revenue = forecast.expected_revenue
        current_opportunities = pipeline_summary.total_opportunities
        current_conversion_rate = self._clamp(
            pipeline_summary.average_completion_rate / _CONVERSION_RATE_SCALE
        )

        revenue_progress = self._ratio(current_revenue, target.target_revenue)
        opportunity_progress = self._ratio(current_opportunities, target.target_opportunities)
        conversion_progress = self._ratio(
            current_conversion_rate, target.target_conversion_rate
        )

        overall_progress = (revenue_progress + opportunity_progress + conversion_progress) / 3

        return SalesTargetProgress(
            target=target,
            current_revenue=current_revenue,
            current_opportunities=current_opportunities,
            current_conversion_rate=current_conversion_rate,
            revenue_progress=revenue_progress,
            opportunity_progress=opportunity_progress,
            conversion_progress=conversion_progress,
            overall_progress=overall_progress,
            is_completed=overall_progress >= 1.0,
            generated_at=now,
        )

    @staticmethod
    def _ratio(current: float, target: float) -> float:
        if target <= 0:
            return 1.0
        return SalesTargetService._clamp(current / target)

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, value))
