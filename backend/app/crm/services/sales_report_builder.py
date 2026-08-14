from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.crm.services.sales_report_section import SalesReportSection


class SalesReportBuilder(BaseModel):
    """A SalesReport prepared for presentation — frozen: just the report's
    own sections, unedited, wrapped with a fixed title/footer and a
    human-readable subtitle. No content is calculated, interpreted, or
    changed here; this is purely a presentation-ready shell around an
    already-built SalesReport.
    """

    model_config = ConfigDict(frozen=True)

    title: str
    subtitle: str
    sections: list[SalesReportSection] = Field(default_factory=list)
    footer: str
    generated_at: datetime
