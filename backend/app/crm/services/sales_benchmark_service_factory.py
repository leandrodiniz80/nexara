from app.crm.services.sales_benchmark_service import SalesBenchmarkService


def build_default_sales_benchmark_service() -> SalesBenchmarkService:
    """Composition root for this service. SalesBenchmarkService has no
    injected collaborator at all — it is a pure, stateless calculator over
    already-built SalesExecutionAnalytics values — so this factory exists
    purely for consistency with every other module's `build_default_*`
    composition root, not because there is anything to wire.
    """
    return SalesBenchmarkService()
