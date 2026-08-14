from typing import Any

from app.decision.models.decision_context import DecisionContext
from app.decision.models.decision_option import DecisionOption


class DecisionBuilder:
    """Constructs DecisionOptions and DecisionContexts — the only place this
    construction logic lives, the same role RuleBuilder/KernelBuilder play for
    their own modules."""

    @staticmethod
    def option(
        *, name: str, score: float, reason: str | None = None, payload: Any | None = None
    ) -> DecisionOption:
        return DecisionOption(name=name, score=score, reason=reason, payload=payload)

    @staticmethod
    def context(
        *,
        variables: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> DecisionContext:
        return DecisionContext(
            variables=variables or {}, metadata=metadata or {}, request_id=request_id
        )
