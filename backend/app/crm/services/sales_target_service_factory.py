from app.crm.services.sales_target_service import SalesTargetService


def build_default_sales_target_service() -> SalesTargetService:
    """Composition root for this service. SalesTargetService has no
    injected collaborator at all — it is a pure, stateless calculator over
    an already-built SalesTarget/SalesForecast/SalesPipelineSummary — so
    this factory exists purely for consistency with every other module's
    `build_default_*` composition root, not because there is anything to
    wire.
    """
    return SalesTargetService()
