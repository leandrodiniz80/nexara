from app.crm.services.sales_playbook_service import SalesPlaybookService


def build_default_sales_playbook_service() -> SalesPlaybookService:
    """Composition root for this service. SalesPlaybookService has no
    injected collaborator at all — like SalesCadenceService and
    ActionPlanningService before it, it is a pure, stateless resolver over a
    fixed lookup table — so this factory exists purely for consistency with
    every other module's `build_default_*` composition root, not because
    there is anything to wire.
    """
    return SalesPlaybookService()
