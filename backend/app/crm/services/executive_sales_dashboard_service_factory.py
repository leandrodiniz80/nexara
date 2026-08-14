from app.crm.services.executive_sales_dashboard_service import ExecutiveSalesDashboardService


def build_default_executive_sales_dashboard_service() -> ExecutiveSalesDashboardService:
    """Composition root for this service. ExecutiveSalesDashboardService has
    no injected collaborator at all — it is a pure, stateless aggregator
    over already-built SalesForecast/SalesTargetProgress/
    SalesPipelineSummary/SalesTrend values — so this factory exists purely
    for consistency with every other module's `build_default_*` composition
    root, not because there is anything to wire.
    """
    return ExecutiveSalesDashboardService()
