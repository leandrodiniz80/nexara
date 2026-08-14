from datetime import datetime, timezone

from app.presentation.executive_view import ExecutiveView
from app.presentation.models.dashboard_view import DashboardView
from app.presentation.models.kpi_view import KPIView
from app.presentation.models.report_view import ReportView


class ExecutiveViewService:
    """Composes an already-built DashboardView, ReportView and
    list[KPIView] into one ExecutiveView — nothing is recalculated, no
    list is altered, no string is modified. It only composes: no domain
    module import, no Engine, no Adapter, no persistence, no integration
    of any kind — it depends on nothing outside this Presentation module.

    PresentationService remains the only place responsible for turning an
    individual domain model into its View Model; this class only ever
    gathers already-built Views into the platform's single reusable
    executive payload.
    """

    def compose(
        self,
        dashboard: DashboardView,
        report: ReportView,
        kpis: list[KPIView],
        *,
        now: datetime | None = None,
    ) -> ExecutiveView:
        now = now or datetime.now(timezone.utc)
        return ExecutiveView(
            dashboard=dashboard,
            report=report,
            kpis=list(kpis),
            generated_at=now,
        )
