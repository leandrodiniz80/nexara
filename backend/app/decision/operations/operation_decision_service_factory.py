from app.decision.operations.operation_decision_service import OperationDecisionService


def build_default_operation_decision_service() -> OperationDecisionService:
    """Composition root for this service. OperationDecisionService has no
    injected collaborator at all — it is a pure, stateless context builder
    — so this factory exists purely for consistency with every other
    module's `build_default_*` composition root, not because there is
    anything to wire.
    """
    return OperationDecisionService()
