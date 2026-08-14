from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.crm.services.executive_sales_dashboard import ExecutiveSalesDashboard
from app.crm.services.sales_kpi_catalog import SalesKPICatalog
from app.crm.services.sales_report_section import SalesReportSection


class SalesReport(BaseModel):
    """The platform's first official executive report — frozen: just the
    ExecutiveSalesDashboard/SalesKPICatalog it was built from, organized
    into SalesReportSections. SalesReportService always returns a new one;
    it never edits a previous SalesReport in place.
    """

    model_config = ConfigDict(frozen=True)

    dashboard: ExecutiveSalesDashboard
    kpis: SalesKPICatalog
    sections: list[SalesReportSection] = Field(default_factory=list)
    generated_at: datetime
