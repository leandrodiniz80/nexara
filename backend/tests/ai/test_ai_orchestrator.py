from typing import Any, ClassVar

import pytest

from app.ai.agents.agent_base import AgentBase
from app.ai.agents.enums import AgentType
from app.ai.exceptions.orchestrator_exceptions import AgentNotRegisteredError, NoProviderAvailableError
from app.ai.exceptions.provider_exceptions import ProviderNotAvailableError
from app.ai.orchestrator.ai_orchestrator import AIOrchestrator
from app.ai.prompts.prompt_repository import PromptRepository
from app.ai.providers.mock_provider import MockProvider
from app.ai.schemas.ai_context import AIContext


class _EchoAgent(AgentBase):
    agent_type: ClassVar[AgentType] = AgentType.RESEARCH
    name: ClassVar[str] = "echo_agent"

    def validate(self, context: AIContext) -> None:
        pass

    def prepare_context(self, context: AIContext) -> dict[str, Any]:
        return {"instruction": context.instruction}

    async def run(self, prepared_context: dict[str, Any]) -> Any:
        return prepared_context["instruction"]

    def post_process(self, raw_output: Any) -> dict[str, Any]:
        return {"echo": raw_output}


def _build_orchestrator() -> AIOrchestrator:
    provider = MockProvider()
    prompt_repository = PromptRepository()
    agent = _EchoAgent(provider, prompt_repository)
    return AIOrchestrator(
        providers={"mock": provider},
        agents={AgentType.RESEARCH: agent},
        prompt_repository=prompt_repository,
    )


def test_select_provider_by_name_and_default():
    orchestrator = _build_orchestrator()
    assert orchestrator.select_provider("mock").provider_name == "mock"
    assert orchestrator.select_provider().provider_name == "mock"


def test_select_provider_unknown_name_raises():
    orchestrator = _build_orchestrator()
    with pytest.raises(ProviderNotAvailableError):
        orchestrator.select_provider("does-not-exist")


def test_select_provider_with_no_providers_raises():
    orchestrator = AIOrchestrator(providers={}, agents={}, prompt_repository=PromptRepository())
    with pytest.raises(NoProviderAvailableError):
        orchestrator.select_provider()


async def test_execute_runs_registered_agent_and_logs_execution():
    orchestrator = _build_orchestrator()
    context = AIContext(instruction="pesquisar Coca-Cola")

    result = await orchestrator.execute(AgentType.RESEARCH, context)

    assert result.success is True
    assert result.payload == {"echo": "pesquisar Coca-Cola"}
    logs = orchestrator.list_execution_logs()
    assert len(logs) == 1
    assert logs[0].agent_name == "echo_agent"


async def test_execute_unregistered_agent_raises():
    orchestrator = _build_orchestrator()
    context = AIContext(instruction="x")
    with pytest.raises(AgentNotRegisteredError):
        await orchestrator.execute(AgentType.COPY, context)


async def test_execute_pipeline_runs_in_sequence_and_logs_each_step():
    orchestrator = _build_orchestrator()
    context = AIContext(instruction="passo 1")

    results = await orchestrator.execute_pipeline([AgentType.RESEARCH], context)

    assert len(results) == 1
    assert results[0].success is True
    assert len(orchestrator.list_execution_logs()) == 1


async def test_real_empty_agent_returns_failed_result_via_factory():
    from app.ai.services.ai_orchestrator_factory import build_default_orchestrator

    orchestrator = build_default_orchestrator()
    context = AIContext(instruction="pesquisar Coca-Cola")

    result = await orchestrator.execute(AgentType.RESEARCH, context)

    assert result.success is False
    assert result.agent_name == "research_agent"
