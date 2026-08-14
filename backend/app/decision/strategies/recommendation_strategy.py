from app.decision.models.decision_context import DecisionContext
from app.decision.models.decision_option import DecisionOption
from app.decision.models.enums import DecisionType
from app.decision.strategies.strategy import Strategy, options_from_variable

_SUPPORTED_TYPES = (
    DecisionType.NEXT_ACTION,
    DecisionType.WORKFLOW,
    DecisionType.AUTOMATION,
    DecisionType.CUSTOM,
)


class RecommendationStrategy(Strategy):
    """Ranks generic recommendations supplied under
    DecisionContext.variables["recommendations"] — each a {"name",
    "confidence", ...} dict. The default fallback for NEXT_ACTION/WORKFLOW/
    AUTOMATION/CUSTOM: all four reduce to "recommend the best named option".
    """

    def supports(self, decision_type: DecisionType) -> bool:
        return decision_type in _SUPPORTED_TYPES

    def decide(self, context: DecisionContext) -> list[DecisionOption]:
        return options_from_variable(context, "recommendations", "confidence")
