from app.operations.coordinator.operations_coordinator import OperationsCoordinator
from app.operations.history.operation_history_service_factory import (
    build_default_operation_history_service,
)
from app.operations.services.operations_engine_factory import build_default_operations_engine


def build_default_operations_coordinator() -> OperationsCoordinator:
    """Composition root for this coordinator. Builds both of its
    collaborators exclusively through their own official factories —
    `build_default_operations_engine()` and
    `build_default_operation_history_service()` — and wires nothing else.
    """
    return OperationsCoordinator(
        build_default_operations_engine(),
        build_default_operation_history_service(),
    )
