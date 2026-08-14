from app.decision.models.decision_context import DecisionContext
from app.decision.models.enums import DecisionType
from app.decision.strategies.priority_strategy import PriorityStrategy


def test_supports_only_priority():
    strategy = PriorityStrategy()

    assert strategy.supports(DecisionType.PRIORITY) is True
    assert strategy.supports(DecisionType.SCORE) is False


def test_decide_converts_candidates_into_options_scored_by_priority():
    context = DecisionContext(
        variables={
            "candidates": [
                {"name": "follow_up", "priority": 2},
                {"name": "escalate", "priority": 5, "reason": "overdue"},
            ]
        }
    )

    options = PriorityStrategy().decide(context)

    assert [o.name for o in options] == ["follow_up", "escalate"]
    assert [o.score for o in options] == [2.0, 5.0]
    assert options[1].reason == "overdue"


def test_decide_returns_no_options_when_no_candidates_are_given():
    options = PriorityStrategy().decide(DecisionContext())

    assert options == []
