from app.decision.models.decision_context import DecisionContext
from app.decision.models.enums import DecisionType
from app.decision.strategies.score_strategy import ScoreStrategy


def test_supports_only_score():
    strategy = ScoreStrategy()

    assert strategy.supports(DecisionType.SCORE) is True
    assert strategy.supports(DecisionType.PRIORITY) is False


def test_decide_passes_through_the_given_scores():
    context = DecisionContext(
        variables={
            "options": [
                {"name": "A", "score": 10, "payload": {"id": 1}},
                {"name": "B", "score": 20},
            ]
        }
    )

    options = ScoreStrategy().decide(context)

    assert [o.name for o in options] == ["A", "B"]
    assert [o.score for o in options] == [10.0, 20.0]
    assert options[0].payload == {"id": 1}


def test_decide_returns_no_options_when_none_are_given():
    options = ScoreStrategy().decide(DecisionContext())

    assert options == []
