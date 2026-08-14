from app.decision.models.decision import Decision
from app.decision.models.enums import DecisionType


class DecisionRepository:
    """In-memory store of every Decision actually made by DecisionEngine.decide()
    — no database, no migration was requested for this module."""

    def __init__(self) -> None:
        self._decisions: list[Decision] = []

    def save_decision(self, decision: Decision) -> Decision:
        self._decisions.append(decision)
        return decision

    def list_decisions(self, *, decision_type: DecisionType | None = None) -> list[Decision]:
        decisions = list(self._decisions)
        if decision_type is not None:
            decisions = [d for d in decisions if d.type == decision_type]
        return decisions
