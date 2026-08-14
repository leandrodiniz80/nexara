from app.crm.services.sales_forecast_service import SalesForecastService


def build_default_sales_forecast_service() -> SalesForecastService:
    """Composition root for this service. SalesForecastService has no
    injected collaborator at all — it is a pure, stateless calculator over
    already-existing CRMOpportunity/CRMPipeline values — so this factory
    exists purely for consistency with every other module's
    `build_default_*` composition root, not because there is anything to
    wire.
    """
    return SalesForecastService()
