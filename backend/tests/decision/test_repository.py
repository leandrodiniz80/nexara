from app.decision.models.decision import Decision
from app.decision.models.enums import DecisionType
from app.decision.repositories.decision_repository import DecisionRepository


def _decision(decision_type: DecisionType, name: str = "chosen", score: float = 1.0) -> Decision:
    return Decision(name=name, type=decision_type, score=score)


def test_save_decision_appends_and_returns_it():
    repository = DecisionRepository()
    decision = _decision(DecisionType.SCORE)

    saved = repository.save_decision(decision)

    assert saved is decision
    assert repository.list_decisions() == [decision]


def test_list_decisions_returns_every_saved_decision_by_default():
    repository = DecisionRepository()
    first = _decision(DecisionType.SCORE, name="a")
    second = _decision(DecisionType.PRIORITY, name="b")
    repository.save_decision(first)
    repository.save_decision(second)

    assert repository.list_decisions() == [first, second]


def test_list_decisions_filters_by_decision_type():
    repository = DecisionRepository()
    score_decision = _decision(DecisionType.SCORE, name="a")
    priority_decision = _decision(DecisionType.PRIORITY, name="b")
    repository.save_decision(score_decision)
    repository.save_decision(priority_decision)

    results = repository.list_decisions(decision_type=DecisionType.PRIORITY)

    assert results == [priority_decision]
