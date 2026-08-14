from app.crm.services.sales_kpi_service import SalesKPIService


def build_default_sales_kpi_service() -> SalesKPIService:
    """Composition root for this service. SalesKPIService has no injected
    collaborator at all — it is a pure, stateless transformer over an
    already-built ExecutiveSalesDashboard — so this factory exists purely
    for consistency with every other module's `build_default_*` composition
    root, not because there is anything to wire.
    """
    return SalesKPIService()
