from app.crm.services.sales_trend_service import SalesTrendService


def build_default_sales_trend_service() -> SalesTrendService:
    """Composition root for this service. SalesTrendService has no injected
    collaborator at all — it is a pure, stateless comparator over two
    already-built SalesTrendSnapshot values — so this factory exists purely
    for consistency with every other module's `build_default_*` composition
    root, not because there is anything to wire.
    """
    return SalesTrendService()
