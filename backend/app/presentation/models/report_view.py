from pydantic import BaseModel, ConfigDict, Field

from app.crm.services.sales_report_section import SalesReportSection


class ReportView(BaseModel):
    """A plain, serialization-ready view of a SalesReportBuilder — frozen:
    every field here is a direct copy of a value SalesReportBuilderService
    already computed, never recalculated. `sections` is copied exactly as
    given — this sprint introduces no new section representation. Built
    for future interfaces (API, Web, Mobile, PDF, HTML, Export) to consume
    instead of the domain object itself.
    """

    model_config = ConfigDict(frozen=True)

    title: str
    subtitle: str
    sections: list[SalesReportSection] = Field(default_factory=list)
    footer: str
