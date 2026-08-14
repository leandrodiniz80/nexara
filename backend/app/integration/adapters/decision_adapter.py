from typing import Any

from app.decision.builders.decision_builder import DecisionBuilder
from app.decision.engine.decision_engine import DecisionEngine
from app.decision.models.enums import DecisionType


class DecisionAdapter:
    """Optional pre-check VerticalSlice consults before invoking Runtime —
    asks the real DecisionEngine which Workflow to run for this execution.
    Returns None (never raises past this class) when the Decision Engine
    can't decide, so the caller can fall back to its own default
    workflow_name — deciding is optional, never a hard requirement.
    """

    def __init__(self, decision_engine: DecisionEngine) -> None:
        self.decision_engine = decision_engine

    def choose_workflow(self, variables: dict[str, Any]) -> str | None:
        context = DecisionBuilder.context(variables=variables)
        result = self.decision_engine.decide(DecisionType.WORKFLOW, context)
        if not result.success or result.selected_option is None:
            return None
        return result.selected_option.name
