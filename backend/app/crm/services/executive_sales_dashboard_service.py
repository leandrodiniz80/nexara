from datetime import datetime, timezone

from app.crm.services.executive_sales_dashboard import ExecutiveHealth, ExecutiveSalesDashboard
from app.crm.services.sales_forecast import SalesForecast
from app.crm.services.sales_pipeline_summary import SalesPipelineSummary
from app.crm.services.sales_target_progress import SalesTargetProgress
from app.crm.services.sales_trend import SalesTrend, SalesTrendDirection

_EXCELLENT_SCORE = 90.0
_GOOD_SCORE = 75.0
_ATTENTION_SCORE = 50.0
_HIGH_CONFIDENCE = 80.0
_LOW_CONFIDENCE = 50.0
_DISTANT_TARGET_PROGRESS = 0.5


class ExecutiveSalesDashboardService:
    """Aggregates an already-built SalesForecast, SalesTargetProgress,
    SalesPipelineSummary and SalesTrend into one consolidated executive
    view — no new business calculation, only a single score/health
    verdict and a fixed set of deterministic highlights/warnings derived
    from values these four services already computed. No persistence, no
    CRMEngine, no Runtime, no Workflow, no Automation, no Adapter, no Rule,
    no Decision, no AI.

    SalesForecastService remains the only place that predicts revenue,
    SalesTargetService the only place that compares against a goal,
    SalesPipelineIntelligenceService the only place that measures
    operational health, and SalesTrendService the only place that compares
    snapshots over time; this class only ever consolidates their output.
    """

    def build(
        self,
        forecast: SalesForecast,
        target_progress: SalesTargetProgress,
        pipeline_summary: SalesPipelineSummary,
        trend: SalesTrend,
        *,
        now: datetime | None = None,
    ) -> ExecutiveSalesDashboard:
        now = now or datetime.now(timezone.utc)

        overall_score = self._overall_score(forecast, target_progress, pipeline_summary)

        return ExecutiveSalesDashboard(
            forecast=forecast,
            target_progress=target_progress,
            pipeline_summary=pipeline_summary,
            trend=trend,
            generated_at=now,
            overall_health=self._overall_health(overall_score),
            overall_score=overall_score,
            highlights=self._highlights(forecast, target_progress, trend),
            warnings=self._warnings(forecast, target_progress, trend),
        )

    @staticmethod
    def _overall_score(
        forecast: SalesForecast,
        target_progress: SalesTargetProgress,
        pipeline_summary: SalesPipelineSummary,
    ) -> float:
        raw = (
            forecast.forecast_confidence
            + target_progress.overall_progress * 100
            + pipeline_summary.average_completion_rate
        ) / 3
        return max(0.0, min(100.0, raw))

    @staticmethod
    def _overall_health(overall_score: float) -> ExecutiveHealth:
        if overall_score >= _EXCELLENT_SCORE:
            return ExecutiveHealth.EXCELLENT
        if overall_score >= _GOOD_SCORE:
            return ExecutiveHealth.GOOD
        if overall_score >= _ATTENTION_SCORE:
            return ExecutiveHealth.ATTENTION
        return ExecutiveHealth.CRITICAL

    @staticmethod
    def _highlights(
        forecast: SalesForecast, target_progress: SalesTargetProgress, trend: SalesTrend
    ) -> list[str]:
        highlights: list[str] = []
        if target_progress.is_completed:
            highlights.append("Meta atingida")
        if trend.is_improving:
            highlights.append("Pipeline crescendo")
        if forecast.forecast_confidence >= _HIGH_CONFIDENCE:
            highlights.append("Alta confiança na previsão")
        return highlights

    @staticmethod
    def _warnings(
        forecast: SalesForecast, target_progress: SalesTargetProgress, trend: SalesTrend
    ) -> list[str]:
        warnings: list[str] = []
        if trend.trend_direction == SalesTrendDirection.DOWN:
            warnings.append("Pipeline em queda")
        if target_progress.overall_progress < _DISTANT_TARGET_PROGRESS:
            warnings.append("Meta distante")
        if forecast.forecast_confidence < _LOW_CONFIDENCE:
            warnings.append("Baixa confiança na previsão")
        return warnings
