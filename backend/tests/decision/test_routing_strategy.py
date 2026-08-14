from app.decision.models.decision_context import DecisionContext
from app.decision.models.enums import DecisionType
from app.decision.strategies.routing_strategy import RoutingStrategy


def test_supports_both_routing_and_channel():
    strategy = RoutingStrategy()

    assert strategy.supports(DecisionType.ROUTING) is True
    assert strategy.supports(DecisionType.CHANNEL) is True
    assert strategy.supports(DecisionType.SCORE) is False


def test_decide_converts_routes_into_options_scored_by_weight():
    context = DecisionContext(
        variables={
            "routes": [
                {"name": "email", "weight": 0.3},
                {"name": "whatsapp", "weight": 0.7},
            ]
        }
    )

    options = RoutingStrategy().decide(context)

    assert [o.name for o in options] == ["email", "whatsapp"]
    assert [o.score for o in options] == [0.3, 0.7]


def test_decide_returns_no_options_when_no_routes_are_given():
    options = RoutingStrategy().decide(DecisionContext())

    assert options == []
