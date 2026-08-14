from app.observability.operations.operation_trace_service import OperationTraceService


def build_default_operation_trace_service() -> OperationTraceService:
    """Composition root for this service. OperationTraceService has no
    injected collaborator at all — it is a pure, stateless builder over an
    already-finished OperationHistory/OperationResult — so this factory
    exists purely for consistency with every other module's
    `build_default_*` composition root, not because there is anything to
    wire.
    """
    return OperationTraceService()
