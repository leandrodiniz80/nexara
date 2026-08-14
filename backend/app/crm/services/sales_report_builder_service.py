from datetime import datetime, timezone

from app.crm.services.sales_report import SalesReport
from app.crm.services.sales_report_builder import SalesReportBuilder

_TITLE = "Executive Sales Report"
_FOOTER = "Generated automatically by Elevel Prospect AI"


class SalesReportBuilderService:
    """Prepares an already-built SalesReport for consumption by future
    presentation layers (PDF, HTML, API, Dashboard, Export) — it only
    organizes: a fixed title, the report's own timestamp formatted as
    ISO8601 for display, its sections copied exactly as-is, and a fixed
    footer. No calculation, no interpretation, no content transformation.
    SalesReportService remains the only place responsible for the logical
    organization of the report's content; this class only ever wraps that
    already-organized content for presentation.
    """

    def build(self, report: SalesReport, *, now: datetime | None = None) -> SalesReportBuilder:
        now = now or datetime.now(timezone.utc)
        return SalesReportBuilder(
            title=_TITLE,
            subtitle=report.generated_at.isoformat(),
            sections=list(report.sections),
            footer=_FOOTER,
            generated_at=now,
        )
