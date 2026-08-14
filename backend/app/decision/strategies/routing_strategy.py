from app.decision.models.decision_context import DecisionContext
from app.decision.models.decision_option import DecisionOption
from app.decision.models.enums import DecisionType
from app.decision.strategies.strategy import Strategy, options_from_variable


class RoutingStrategy(Strategy):
    """Ranks named routes supplied under DecisionContext.variables["routes"] —
    each a {"name", "weight", ...} dict. Supports both ROUTING and CHANNEL: in
    both cases the decision is "which named destination, weighted how".
    """

    def supports(self, decision_type: DecisionType) -> bool:
        return decision_type in (DecisionType.ROUTING, DecisionType.CHANNEL)

    def decide(self, context: DecisionContext) -> list[DecisionOption]:
        return options_from_variable(context, "routes", "weight")
