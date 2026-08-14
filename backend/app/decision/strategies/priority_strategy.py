from app.decision.models.decision_context import DecisionContext
from app.decision.models.decision_option import DecisionOption
from app.decision.models.enums import DecisionType
from app.decision.strategies.strategy import Strategy, options_from_variable


class PriorityStrategy(Strategy):
    """Ranks candidates supplied under DecisionContext.variables["candidates"] —
    each a {"name", "priority", ...} dict — by their integer priority, the
    higher the priority the higher the resulting DecisionOption.score.
    """

    def supports(self, decision_type: DecisionType) -> bool:
        return decision_type == DecisionType.PRIORITY

    def decide(self, context: DecisionContext) -> list[DecisionOption]:
        return options_from_variable(context, "candidates", "priority")
