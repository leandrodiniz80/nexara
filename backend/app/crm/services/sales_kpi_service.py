from datetime import datetime, timezone

from app.crm.services.executive_sales_dashboard import ExecutiveSalesDashboard
from app.crm.services.sales_kpi import SalesKPI
from app.crm.services.sales_kpi_catalog import SalesKPICatalog

_GOOD_THRESHOLD = 75.0
_ATTENTION_THRESHOLD = 50.0
_INFO_STATUS = "INFO"


class SalesKPIService:
    """Turns an already-built ExecutiveSalesDashboard into a standardized
    catalog of executive KPIs — no new business calculation, only
    relabeling values the platform's other services already computed. No
    persistence, no CRMEngine, no Runtime, no Workflow, no Automation, no
    Adapter, no Rule, no Decision, no AI.

    ExecutiveSalesDashboardService remains the only place that consolidates
    the executive view; this class only ever reformats its already-computed
    figures into the platform's official KPI shape. `overall_score` is
    copied through from the dashboard exactly as-is — never recalculated.
    """

    def build(
        self, dashboard: ExecutiveSalesDashboard, *, now: datetime | None = None
    ) -> SalesKPICatalog:
        now = now or datetime.now(timezone.utc)

        kpis = [
            self._numeric_kpi(
                name="Forecast Confidence",
                value=dashboard.forecast.forecast_confidence,
                unit="%",
                description="Confiança da previsão de receita.",
                now=now,
            ),
            self._numeric_kpi(
                name="Target Progress",
                value=dashboard.target_progress.overall_progress * 100,
                unit="%",
                description="Progresso em relação à meta comercial.",
                now=now,
            ),
            self._numeric_kpi(
                name="Pipeline Completion",
                value=dashboard.pipeline_summary.average_completion_rate,
                unit="%",
                description="Taxa média de conclusão das cadências do pipeline.",
                now=now,
            ),
            self._numeric_kpi(
                name="Revenue Forecast",
                value=dashboard.forecast.expected_revenue,
                unit="R$",
                description="Receita esperada com base na previsão atual.",
                now=now,
            ),
            self._textual_kpi(
                name="Pipeline Health",
                value=dashboard.overall_health.value,
                description="Saúde geral do pipeline comercial.",
                now=now,
            ),
            self._textual_kpi(
                name="Trend Direction",
                value=dashboard.trend.trend_direction.value,
                description="Direção da tendência comercial.",
                now=now,
            ),
        ]

        return SalesKPICatalog(kpis=kpis, overall_score=dashboard.overall_score, generated_at=now)

    @classmethod
    def _numeric_kpi(
        cls, *, name: str, value: float, unit: str, description: str, now: datetime
    ) -> SalesKPI:
        return SalesKPI(
            name=name,
            value=value,
            unit=unit,
            status=cls._status(value),
            description=description,
            generated_at=now,
        )

    @staticmethod
    def _textual_kpi(*, name: str, value: str, description: str, now: datetime) -> SalesKPI:
        return SalesKPI(
            name=name,
            value=value,
            unit="texto",
            status=_INFO_STATUS,
            description=description,
            generated_at=now,
        )

    @staticmethod
    def _status(value: float) -> str:
        if value >= _GOOD_THRESHOLD:
            return "GOOD"
        if value >= _ATTENTION_THRESHOLD:
            return "ATTENTION"
        return "CRITICAL"
