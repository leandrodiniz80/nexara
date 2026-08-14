from abc import ABC, abstractmethod

from app.decision.models.decision_context import DecisionContext
from app.decision.models.decision_option import DecisionOption
from app.decision.models.enums import DecisionType


class Strategy(ABC):
    """Contract every decision Strategy satisfies. A Strategy never picks a
    winner — it only proposes candidate DecisionOptions for a DecisionContext;
    DecisionEngine.decide() is the only place that chooses among them.
    """

    @abstractmethod
    def supports(self, decision_type: DecisionType) -> bool:
        """Whether this Strategy knows how to produce options for the given
        DecisionType."""

    @abstractmethod
    def decide(self, context: DecisionContext) -> list[DecisionOption]:
        """Return every candidate DecisionOption this Strategy can propose for
        the given DecisionContext — never fewer than zero, never a single
        pre-selected winner."""


def options_from_variable(
    context: DecisionContext, variable_key: str, score_field: str
) -> list[DecisionOption]:
    """Shared helper every default Strategy uses to turn a generic list of dicts
    under `context.variables[variable_key]` into DecisionOptions. No Strategy
    hardcodes what any of those dicts *mean* — only which keys their own
    generic shape uses (e.g. "priority" vs "score" vs "weight").
    """
    entries = context.variables.get(variable_key, [])
    return [
        DecisionOption(
            name=entry["name"],
            score=float(entry[score_field]),
            reason=entry.get("reason"),
            payload=entry.get("payload"),
        )
        for entry in entries
    ]
