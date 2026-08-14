from app.observability.operations.observability_operations_service import (
    ObservabilityOperationsService,
)
from app.observability.operations.operation_trace_service_factory import (
    build_default_operation_trace_service,
)
from app.observability.services.observability_engine_factory import (
    build_default_observability_engine,
)


def build_default_observability_operations_service() -> ObservabilityOperationsService:
    """Composition root for this service. Builds both of its collaborators
    exclusively through their own official factories —
    `build_default_observability_engine()` and
    `build_default_operation_trace_service()` — and wires nothing else.
    """
    return ObservabilityOperationsService(
        build_default_observability_engine(),
        build_default_operation_trace_service(),
    )
