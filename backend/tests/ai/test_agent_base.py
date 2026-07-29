from typing import Any, ClassVar

import pytest

from app.ai.agents.agent_base import AgentBase
from app.ai.agents.enums import AgentType
from app.ai.prompts.prompt_repository import PromptRepository
from app.ai.providers.mock_provider import MockProvider
from app.ai.schemas.ai_context import AIContext


class _DummyAgent(AgentBase):
    agent_type: ClassVar[AgentType] = AgentType.RESEARCH
    name: ClassVar[str] = "dummy_agent"

    def validate(self, context: AIContext) -> None:
        if context.instruction is None:
            raise ValueError("instruction is required")

    def prepare_context(self, context: AIContext) -> dict[str, Any]:
        return {"instruction": context.instruction}

    async def run(self, prepared_context: dict[str, Any]) -> Any:
        return f"done: {prepared_context['instruction']}"

    def post_process(self, raw_output: Any) -> dict[str, Any]:
        return {"result": raw_output}


class _BrokenAgent(_DummyAgent):
    name: ClassVar[str] = "broken_agent"

    async def run(self, prepared_context: dict[str, Any]) -> Any:
        raise RuntimeError("boom")


async def test_agent_base_execute_success_path():
    agent = _DummyAgent(MockProvider(), PromptRepository())
    context = AIContext(instruction="pesquisar empresa")

    result = await agent.execute(context)

    assert result.success is True
    assert result.agent_name == "dummy_agent"
    assert result.payload == {"result": "done: pesquisar empresa"}
    assert result.execution_time >= 0
    assert result.provider == "mock"


async def test_agent_base_execute_wraps_validation_failure():
    agent = _DummyAgent(MockProvider(), PromptRepository())
    context = AIContext(instruction=None)

    result = await agent.execute(context)

    assert result.success is False
    assert result.payload is None
    assert any("failed" in log for log in result.logs)


async def test_agent_base_execute_wraps_run_failure():
    agent = _BrokenAgent(MockProvider(), PromptRepository())
    context = AIContext(instruction="algo")

    result = await agent.execute(context)

    assert result.success is False


def test_agent_base_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        AgentBase(MockProvider(), PromptRepository())
