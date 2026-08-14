import pytest
from pydantic import ValidationError

from app.decision.builders.decision_builder import DecisionBuilder


def test_option_builds_a_decision_option():
    option = DecisionBuilder.option(name="send_proposal", score=0.8, reason="high confidence")

    assert option.name == "send_proposal"
    assert option.score == 0.8
    assert option.reason == "high confidence"
    assert option.payload is None


def test_option_is_frozen():
    option = DecisionBuilder.option(name="send_proposal", score=0.8)

    with pytest.raises(ValidationError):
        option.score = 1.0


def test_context_builds_with_defaults_when_nothing_is_given():
    context = DecisionBuilder.context()

    assert context.variables == {}
    assert context.metadata == {}
    assert context.request_id is None


def test_context_builds_with_the_given_variables_and_request_id():
    context = DecisionBuilder.context(variables={"score": 80}, request_id="req-1")

    assert context.variables == {"score": 80}
    assert context.request_id == "req-1"
