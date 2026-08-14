from app.crm.services.executive_sales_dashboard import ExecutiveSalesDashboard
from app.crm.services.sales_kpi_catalog import SalesKPICatalog
from app.crm.services.sales_report_builder import SalesReportBuilder
from app.presentation.models.dashboard_view import DashboardView
from app.presentation.models.kpi_view import KPIView
from app.presentation.models.report_view import ReportView


class PresentationService:
    """Converts already-computed commercial domain models into plain View
    Models — no calculation, no rule, no integration. Every field on every
    View Model it produces is a direct copy of a value some CRM service
    already computed: no CRMEngine, no Runtime, no Workflow, no Automation,
    no AI, no Rule, no Decision, no Adapter, no persistence.

    Every CRM service upstream (ExecutiveSalesDashboardService,
    SalesKPIService, SalesReportBuilderService, and everything they build
    on) remains responsible for the domain; this class only ever reshapes
    their already-finished output into the plain, serialization-ready
    shape future interfaces (API, Web, Mobile, PDF, HTML, Export) expect.
    """

    def to_dashboard_view(self, dashboard: ExecutiveSalesDashboard) -> DashboardView:
        cards = [
            {"label": "Expected Revenue", "value": dashboard.forecast.expected_revenue},
            {"label": "Forecast Confidence", "value": dashboard.forecast.forecast_confidence},
            {
                "label": "Target Progress",
                "value": dashboard.target_progress.overall_progress,
            },
            {
                "label": "Pipeline Completion",
                "value": dashboard.pipeline_summary.average_completion_rate,
            },
            {
                "label": "Pipeline Health",
                "value": dashboard.pipeline_summary.overall_health.value,
            },
            {"label": "Trend Direction", "value": dashboard.trend.trend_direction.value},
        ]
        return DashboardView(
            title="Sales Dashboard",
            overall_health=dashboard.overall_health.value,
            overall_score=dashboard.overall_score,
            cards=cards,
            highlights=list(dashboard.highlights),
            warnings=list(dashboard.warnings),
            generated_at=dashboard.generated_at,
        )

    def to_kpi_views(self, catalog: SalesKPICatalog) -> list[KPIView]:
        return [
            KPIView(name=kpi.name, value=kpi.value, unit=kpi.unit, status=kpi.status)
            for kpi in catalog.kpis
        ]

    def to_report_view(self, report_builder: SalesReportBuilder) -> ReportView:
        return ReportView(
            title=report_builder.title,
            subtitle=report_builder.subtitle,
            sections=list(report_builder.sections),
            footer=report_builder.footer,
        )
