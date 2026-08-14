from app.crm.services.sales_execution_analytics_service import SalesExecutionAnalyticsService


def build_default_sales_execution_analytics_service() -> SalesExecutionAnalyticsService:
    """Composition root for this service. SalesExecutionAnalyticsService has
    no injected collaborator at all — it is a pure, stateless calculator
    over an already-built SalesEnrollment/SalesTimeline — so this factory
    exists purely for consistency with every other module's
    `build_default_*` composition root, not because there is anything to
    wire.
    """
    return SalesExecutionAnalyticsService()
