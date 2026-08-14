from app.crm.services.sales_pipeline_intelligence_service import (
    SalesPipelineIntelligenceService,
)


def build_default_sales_pipeline_intelligence_service() -> SalesPipelineIntelligenceService:
    """Composition root for this service. SalesPipelineIntelligenceService
    has no injected collaborator at all — it is a pure, stateless
    aggregator over already-built SalesExecutionAnalytics/SalesCoachingResult
    pairs — so this factory exists purely for consistency with every other
    module's `build_default_*` composition root, not because there is
    anything to wire.
    """
    return SalesPipelineIntelligenceService()
