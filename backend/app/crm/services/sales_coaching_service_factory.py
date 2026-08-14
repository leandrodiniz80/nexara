from app.crm.services.sales_coaching_service import SalesCoachingService


def build_default_sales_coaching_service() -> SalesCoachingService:
    """Composition root for this service. SalesCoachingService has no
    injected collaborator at all — it is a pure, stateless calculator over
    an already-built SalesExecutionAnalytics/SalesBenchmarkResult — so this
    factory exists purely for consistency with every other module's
    `build_default_*` composition root, not because there is anything to
    wire.
    """
    return SalesCoachingService()
