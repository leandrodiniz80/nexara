from datetime import datetime, timezone

from app.crm.services.executive_sales_dashboard import ExecutiveSalesDashboard
from app.crm.services.sales_kpi_catalog import SalesKPICatalog
from app.crm.services.sales_report import SalesReport
from app.crm.services.sales_report_section import SalesReportSection


class SalesReportService:
    """Organizes an already-built ExecutiveSalesDashboard and
    SalesKPICatalog into the platform's first official executive report —
    no new calculation, no new rule, only copying existing values into four
    fixed sections. No persistence, no CRMEngine, no Runtime, no Workflow,
    no Automation, no Adapter, no Rule, no Decision, no AI.

    ExecutiveSalesDashboardService remains the only place that consolidates
    the executive view, and SalesKPIService remains the only place that
    standardizes indicators; this class only ever arranges their
    already-computed output into a structured report.
    """

    def build(
        self,
        dashboard: ExecutiveSalesDashboard,
        kpis: SalesKPICatalog,
        *,
        now: datetime | None = None,
    ) -> SalesReport:
        now = now or datetime.now(timezone.utc)

        sections = [
            SalesReportSection(
                title="Resumo Executivo",
                items={
                    "overall_health": dashboard.overall_health,
                    "overall_score": dashboard.overall_score,
                    "highlights": list(dashboard.highlights),
                    "warnings": list(dashboard.warnings),
                },
            ),
            SalesReportSection(
                title="Financeiro",
                items={
                    "expected_revenue": dashboard.forecast.expected_revenue,
                    "forecast_confidence": dashboard.forecast.forecast_confidence,
                    "target_progress": dashboard.target_progress.overall_progress,
                },
            ),
            SalesReportSection(
                title="Pipeline",
                items={
                    "pipeline_health": dashboard.pipeline_summary.overall_health,
                    "completion_rate": dashboard.pipeline_summary.average_completion_rate,
                    "trend_direction": dashboard.trend.trend_direction,
                },
            ),
            SalesReportSection(
                title="Indicadores",
                items={"kpis": list(kpis.kpis)},
            ),
        ]

        return SalesReport(dashboard=dashboard, kpis=kpis, sections=sections, generated_at=now)
