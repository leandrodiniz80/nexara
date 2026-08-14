from app.decision.engine.decision_engine_factory import build_default_decision_engine
from app.decision.operations.decision_operations_service import DecisionOperationsService
from app.decision.operations.operation_decision_service_factory import (
    build_default_operation_decision_service,
)


def build_default_decision_operations_service() -> DecisionOperationsService:
    """Composition root for this service. Builds both of its collaborators
    exclusively through their own official factories —
    `build_default_decision_engine()` and
    `build_default_operation_decision_service()` — and wires nothing else.
    """
    return DecisionOperationsService(
        build_default_decision_engine(),
        build_default_operation_decision_service(),
    )
