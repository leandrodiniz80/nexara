from app.crm.engine.crm_engine import CRMEngine
from app.crm.services.crm_engine_factory import build_default_crm_engine
from app.crm.services.next_action_service import NextActionService


def build_default_next_action_service(*, crm_engine: CRMEngine | None = None) -> NextActionService:
    """Composition root for this service — calls the existing
    build_default_crm_engine() Factory directly, never constructing a
    CRMEngine by hand.

    Mirrors opportunity_lifecycle_service_factory.build_default_opportunity_lifecycle_service()
    exactly, including deliberately not routing through Bootstrap: this file
    lives inside app.crm.services, the very package app.bootstrap.builders
    itself imports from (build_default_crm_engine), so importing
    app.bootstrap here would risk a real circular import.
    """
    return NextActionService(crm_engine or build_default_crm_engine())
