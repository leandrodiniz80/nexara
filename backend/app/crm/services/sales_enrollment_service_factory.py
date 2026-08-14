from app.crm.services.sales_cadence_execution_service_factory import (
    build_default_sales_cadence_execution_service,
)
from app.crm.services.sales_enrollment_service import SalesEnrollmentService


def build_default_sales_enrollment_service() -> SalesEnrollmentService:
    """Composition root for this service. Its only collaborator is the
    already-existing SalesCadenceExecutionService, wired here exclusively
    through `build_default_sales_cadence_execution_service()` — no Bootstrap,
    no Engine, no new wiring of any kind.
    """
    return SalesEnrollmentService(build_default_sales_cadence_execution_service())
