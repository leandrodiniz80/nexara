from app.decision.models.decision_context import DecisionContext
from app.decision.models.decision_option import DecisionOption
from app.decision.models.enums import DecisionType
from app.decision.strategies.strategy import Strategy, options_from_variable


class ScoreStrategy(Strategy):
    """Wraps candidates already scored by the caller under
    DecisionContext.variables["options"] — each a {"name", "score", ...} dict —
    directly into DecisionOptions, a pure pass-through.
    """

    def supports(self, decision_type: DecisionType) -> bool:
        return decision_type == DecisionType.SCORE

    def decide(self, context: DecisionContext) -> list[DecisionOption]:
        return options_from_variable(context, "options", "score")
