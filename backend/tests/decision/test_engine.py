from app.decision.builders.decision_builder import DecisionBuilder
from app.decision.engine.decision_engine import DecisionEngine
from app.decision.engine.decision_engine_factory import build_default_decision_engine
from app.decision.models.decision_context import DecisionContext
from app.decision.models.enums import DecisionType
from app.decision.registry.strategy_registry import StrategyRegistry
from app.decision.repositories.decision_repository import DecisionRepository
from app.decision.strategies.score_strategy import ScoreStrategy


def test_register_strategy_adds_it_to_the_registry_and_list_strategies_reflects_it():
    engine = DecisionEngine(registry=StrategyRegistry(), repository=DecisionRepository())
    strategy = ScoreStrategy()

    engine.register_strategy(strategy)

    assert engine.list_strategies() == [strategy]


def test_decide_selects_the_highest_scoring_option():
    engine = build_default_decision_engine()
    context = DecisionBuilder.context(
        variables={"options": [{"name": "A", "score": 10}, {"name": "B", "score": 20}]}
    )

    result = engine.decide(DecisionType.SCORE, context)

    assert result.success is True
    assert result.selected_option.name == "B"
    assert [o.name for o in result.candidate_options] == ["A", "B"]
    assert result.execution_time >= 0
    assert result.reason is None


def test_decide_persists_the_selected_decision_in_the_repository():
    engine = build_default_decision_engine()
    context = DecisionBuilder.context(variables={"options": [{"name": "A", "score": 5}]})

    result = engine.decide(DecisionType.SCORE, context, priority=3)

    saved = engine.repository.list_decisions(decision_type=DecisionType.SCORE)
    assert len(saved) == 1
    assert saved[0].name == result.selected_option.name
    assert saved[0].priority == 3
    assert saved[0].score == result.selected_option.score


def test_decide_for_an_unregistered_type_fails_gracefully_instead_of_raising():
    engine = DecisionEngine(registry=StrategyRegistry(), repository=DecisionRepository())

    result = engine.decide(DecisionType.SCORE, DecisionContext())

    assert result.success is False
    assert result.selected_option is None
    assert result.candidate_options == []
    assert "DecisionType.SCORE" in result.reason


def test_decide_with_no_candidates_fails_gracefully_instead_of_raising():
    engine = build_default_decision_engine()

    result = engine.decide(DecisionType.SCORE, DecisionContext())

    assert result.success is False
    assert result.selected_option is None
    assert result.reason is not None


def test_decide_all_evaluates_every_decision_type():
    engine = build_default_decision_engine()
    context = DecisionBuilder.context(
        variables={
            "options": [{"name": "A", "score": 1}],
            "candidates": [{"name": "B", "priority": 1}],
        }
    )

    results = engine.decide_all([DecisionType.SCORE, DecisionType.PRIORITY], context)

    assert [r.selected_option.name for r in results] == ["A", "B"]


def test_decision_engine_never_imports_any_forbidden_module():
    import app.decision.engine.decision_engine as module

    with open(module.__file__, encoding="utf-8") as source_file:
        source = source_file.read()

    for forbidden in (
        "app.workflows",
        "app.automation",
        "app.runtime",
        "app.crm",
        "app.mission",
        "app.research",
        "app.ai",
        "app.business_rules",
        "app.platform",
        "app.application",
        "app.api",
        "app.observability",
    ):
        assert forbidden not in source
