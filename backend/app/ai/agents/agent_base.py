import time
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from app.ai.agents.enums import AgentType
from app.ai.providers.base.ai_provider import AIProvider
from app.ai.prompts.prompt_repository import PromptRepository
from app.ai.schemas.agent_result import AgentResult
from app.ai.schemas.ai_context import AIContext


class AgentBase(ABC):
    """Base class for every AI agent (Research, Qualification, Enrichment, ...).

    `execute()` is a concrete template method: validate -> prepare_context -> run ->
    post_process, timed and always wrapped into an AgentResult — even on failure, so a
    broken/unimplemented agent can never raise past the orchestrator boundary. The four
    hooks (`validate`, `prepare_context`, `run`, `post_process`) are what a concrete
    agent overrides. `run()` is the one hook beyond the four named in the spec: it is
    where the actual AIProvider call happens, kept separate from `prepare_context`/
    `post_process` so each hook has exactly one responsibility.
    """

    agent_type: ClassVar[AgentType]
    name: ClassVar[str]

    def __init__(self, provider: AIProvider, prompt_repository: PromptRepository) -> None:
        self.provider = provider
        self.prompt_repository = prompt_repository

    async def execute(self, context: AIContext) -> AgentResult:
        start = time.perf_counter()
        logs: list[str] = []
        try:
            self.validate(context)
            prepared = self.prepare_context(context)
            logs.append(f"{self.name}: context prepared")
            raw_output = await self.run(prepared)
            payload = self.post_process(raw_output)
            return AgentResult(
                success=True,
                agent_name=self.name,
                execution_time=time.perf_counter() - start,
                provider=getattr(self.provider, "provider_name", None),
                model=getattr(self.provider, "default_model", None),
                payload=payload,
                logs=logs,
            )
        except Exception as exc:  # an agent must never raise past the orchestrator
            logs.append(f"{self.name}: failed - {exc}")
            return AgentResult(
                success=False,
                agent_name=self.name,
                execution_time=time.perf_counter() - start,
                provider=getattr(self.provider, "provider_name", None),
                model=getattr(self.provider, "default_model", None),
                payload=None,
                logs=logs,
            )

    @abstractmethod
    def validate(self, context: AIContext) -> None:
        """Raise AgentValidationError if `context` is missing what this agent needs."""

    @abstractmethod
    def prepare_context(self, context: AIContext) -> dict[str, Any]:
        """Turn AIContext into the concrete prompt variables / provider call arguments."""

    @abstractmethod
    async def run(self, prepared_context: dict[str, Any]) -> Any:
        """Call the provider (via self.provider / self.prompt_repository) and return the raw output."""

    @abstractmethod
    def post_process(self, raw_output: Any) -> dict[str, Any]:
        """Shape the provider's raw output into the AgentResult.payload."""
