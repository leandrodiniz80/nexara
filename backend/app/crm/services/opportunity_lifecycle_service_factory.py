from app.crm.engine.crm_engine import CRMEngine
from app.crm.services.crm_engine_factory import build_default_crm_engine
from app.crm.services.opportunity_lifecycle_service import OpportunityLifecycleService


def build_default_opportunity_lifecycle_service(
    *, crm_engine: CRMEngine | None = None
) -> OpportunityLifecycleService:
    """Composition root for this service — calls the existing
    build_default_crm_engine() Factory directly, never constructing a
    CRMEngine by hand.

    Deliberately does not route through Bootstrap the way
    execution_service_factory/execution_result_processor_factory do: this
    file lives inside app.crm.services, the very package
    app.bootstrap.builders itself imports from (build_default_crm_engine), so
    importing app.bootstrap here would risk a real circular import the
    moment anything imports this module before app.bootstrap has finished
    initializing. Calling the CRM module's own existing Factory directly
    avoids that risk entirely while still using only existing
    infrastructure.
    """
    return OpportunityLifecycleService(crm_engine or build_default_crm_engine())
