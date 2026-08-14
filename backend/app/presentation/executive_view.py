from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.presentation.models.dashboard_view import DashboardView
from app.presentation.models.kpi_view import KPIView
from app.presentation.models.report_view import ReportView


class ExecutiveView(BaseModel):
    """The single, composed payload representing the platform's entire
    executive view — frozen: just a DashboardView, a ReportView and a
    list[KPIView] already built by PresentationService, held together.
    This is the standard payload future interfaces (API, Web Dashboard,
    Mobile, Export) are meant to consume.
    """

    model_config = ConfigDict(frozen=True)

    dashboard: DashboardView
    report: ReportView
    kpis: list[KPIView] = Field(default_factory=list)
    generated_at: datetime
