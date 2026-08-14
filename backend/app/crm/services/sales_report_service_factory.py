from app.crm.services.sales_report_service import SalesReportService


def build_default_sales_report_service() -> SalesReportService:
    """Composition root for this service. SalesReportService has no
    injected collaborator at all — it is a pure, stateless organizer over
    an already-built ExecutiveSalesDashboard/SalesKPICatalog — so this
    factory exists purely for consistency with every other module's
    `build_default_*` composition root, not because there is anything to
    wire.
    """
    return SalesReportService()
