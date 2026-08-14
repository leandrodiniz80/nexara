from app.operations.history.operation_history_service import OperationHistoryService


def build_default_operation_history_service() -> OperationHistoryService:
    """Composition root for this service. OperationHistoryService has no
    injected collaborator at all — it is a pure, stateless recorder — so
    this factory exists purely for consistency with every other module's
    `build_default_*` composition root, not because there is anything to
    wire.
    """
    return OperationHistoryService()
