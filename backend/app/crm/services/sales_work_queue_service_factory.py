from app.crm.services.sales_work_queue_service import SalesWorkQueueService


def build_default_sales_work_queue_service() -> SalesWorkQueueService:
    """Composition root for this service. SalesWorkQueueService has no
    injected collaborator at all — like ActionPlanningService, it is a pure,
    stateless organizer over whatever ActionPlans its caller already has —
    so this factory exists purely for consistency with every other module's
    `build_default_*` composition root, not because there is anything to
    wire.
    """
    return SalesWorkQueueService()
