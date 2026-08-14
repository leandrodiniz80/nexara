from app.decision.operations.operation_decision_context import OperationDecisionContext
from app.observability.operations.operation_trace import OperationTrace
from app.operations.coordinator.operation_result import OperationResult
from app.operations.history.operation_history import OperationHistory


class OperationDecisionService:
    """Builds a standardized OperationDecisionContext from an
    OperationHistory, OperationResult, and OperationTrace — nothing more.
    It decides absolutely nothing, never calls DecisionEngine, and knows
    exclusively these three types.
    """

    def build_context(
        self,
        history: OperationHistory,
        result: OperationResult,
        trace: OperationTrace,
    ) -> OperationDecisionContext:
        return OperationDecisionContext(
            operation_history=history,
            operation_result=result,
            operation_trace=trace,
        )
