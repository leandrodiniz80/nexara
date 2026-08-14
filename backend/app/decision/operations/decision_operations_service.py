from typing import Any

from app.decision.engine.decision_engine import DecisionEngine
from app.decision.models.decision_context import DecisionContext
from app.decision.models.decision_result import DecisionResult
from app.decision.models.enums import DecisionType
from app.decision.operations.operation_decision_context import OperationDecisionContext
from app.decision.operations.operation_decision_service import OperationDecisionService
from app.observability.operations.operation_trace import OperationTrace
from app.operations.coordinator.operation_result import OperationResult
from app.operations.history.operation_history import OperationHistory

_DECISION_TYPE = DecisionType.SCORE
_PROCEED_OPTION = "proceed"
_RETRY_OPTION = "retry"


class DecisionOperationsService:
    """Adapts Operations' operational data into DecisionEngine's existing
    public API — no new Strategy, no change to DecisionEngine.

    It knows exclusively DecisionEngine and OperationDecisionService:
    `evaluate()` first asks OperationDecisionService to build the
    OperationDecisionContext for an already-finished OperationHistory/
    OperationResult/OperationTrace, then translates that context into a
    DecisionContext DecisionEngine's own ScoreStrategy already understands
    — two generic candidates, "proceed" and "retry", scored deterministically
    from whether the operation succeeded — and calls DecisionEngine.decide().
    This mirrors the same start/adapt/delegate shape
    ObservabilityOperationsService already uses for Operations' history.
    """

    def __init__(
        self,
        decision_engine: DecisionEngine,
        operation_decision_service: OperationDecisionService,
    ) -> None:
        self._decision_engine = decision_engine
        self._operation_decision_service = operation_decision_service

    def evaluate(
        self,
        history: OperationHistory,
        result: OperationResult,
        trace: OperationTrace,
    ) -> DecisionResult:
        context = self._operation_decision_service.build_context(history, result, trace)
        decision_context = self._to_decision_context(context)
        return self._decision_engine.decide(_DECISION_TYPE, decision_context)

    @staticmethod
    def _to_decision_context(context: OperationDecisionContext) -> DecisionContext:
        success = context.operation_result.success
        options: list[dict[str, Any]] = [
            {
                "name": _PROCEED_OPTION,
                "score": 1.0 if success else 0.0,
                "reason": "Operation succeeded." if success else "Operation failed.",
            },
            {
                "name": _RETRY_OPTION,
                "score": 0.0 if success else 1.0,
                "reason": "Operation succeeded." if success else "Operation failed.",
            },
        ]
        return DecisionContext(
            variables={"options": options},
            metadata={"operation_id": str(context.operation_history.operation_id)},
        )
