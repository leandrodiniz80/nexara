from app.crm.services.sales_report_builder_service import SalesReportBuilderService


def build_default_sales_report_builder_service() -> SalesReportBuilderService:
    """Composition root for this service. SalesReportBuilderService has no
    injected collaborator at all — it is a pure, stateless wrapper over an
    already-built SalesReport — so this factory exists purely for
    consistency with every other module's `build_default_*` composition
    root, not because there is anything to wire.
    """
    return SalesReportBuilderService()
