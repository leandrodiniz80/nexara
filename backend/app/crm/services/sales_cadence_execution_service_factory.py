from app.crm.services.sales_cadence_execution_service import SalesCadenceExecutionService


def build_default_sales_cadence_execution_service() -> SalesCadenceExecutionService:
    """Composition root for this service. SalesCadenceExecutionService has no
    injected collaborator at all — like SalesCadenceService and
    ActionPlanningService before it, it is a pure, stateless controller over
    whatever SalesCadence/SalesCadenceExecution its caller already has — so
    this factory exists purely for consistency with every other module's
    `build_default_*` composition root, not because there is anything to
    wire.
    """
    return SalesCadenceExecutionService()
