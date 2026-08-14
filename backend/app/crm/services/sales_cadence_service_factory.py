from app.crm.services.sales_cadence_service import SalesCadenceService


def build_default_sales_cadence_service() -> SalesCadenceService:
    """Composition root for this service. SalesCadenceService has no
    injected collaborator at all — like ActionPlanningService and
    SalesWorkQueueService, it is a pure, stateless calculator over whatever
    CRMOpportunity/ActionPlan/SalesWorkQueueItem its caller already has — so
    this factory exists purely for consistency with every other module's
    `build_default_*` composition root, not because there is anything to
    wire.
    """
    return SalesCadenceService()
