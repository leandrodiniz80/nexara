from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.presentation.models.dashboard_view import DashboardView
from app.presentation.models.kpi_view import KPIView
from app.presentation.models.report_view import ReportView


class ExecutivePayload(BaseModel):
    """The public, serializable DTO for the platform's executive view —
    frozen, and completely decoupled from the domain: it holds only
    Presentation-layer Views (DashboardView, ReportView, list[KPIView]) and
    plain metadata, never a domain object. This is not an API response, not
    JSON, not HTTP — just the transport-ready shape those future layers
    will build on top of.
    """

    model_config = ConfigDict(frozen=True)

    title: str
    generated_at: datetime
    dashboard: DashboardView
    report: ReportView
    kpis: list[KPIView] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
