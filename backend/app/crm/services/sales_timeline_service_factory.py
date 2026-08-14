from app.crm.services.sales_timeline_service import SalesTimelineService


def build_default_sales_timeline_service() -> SalesTimelineService:
    """Composition root for this service. SalesTimelineService has no
    injected collaborator at all — it is a pure, stateless recorder that
    only ever builds new SalesTimeline/SalesTimelineEvent values from data
    its caller already has — so this factory exists purely for consistency
    with every other module's `build_default_*` composition root, not
    because there is anything to wire.
    """
    return SalesTimelineService()
