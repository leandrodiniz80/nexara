from app.ai.agents.agent_base import AgentBase
from app.ai.agents.enums import AgentType
from app.ai.exceptions.orchestrator_exceptions import AgentNotRegisteredError, NoProviderAvailableError
from app.ai.exceptions.provider_exceptions import ProviderNotAvailableError
from app.ai.prompts.prompt_repository import PromptRepository
from app.ai.providers.base.ai_provider import AIProvider
from app.ai.schemas.agent_result import AgentResult
from app.ai.schemas.ai_context import AIContext
from app.ai.schemas.ai_execution_log import AIExecutionLog


class AIOrchestrator:
    """The single mandatory door for every AI call on the platform.

    No Service is allowed to talk to an AIProvider directly — it calls
    `AIOrchestrator.execute()`. This is what lets providers/agents/prompts be swapped
    or added without ever touching business logic (Dependency Inversion).
    """

    def __init__(
        self,
        providers: dict[str, AIProvider],
        agents: dict[AgentType, AgentBase],
        prompt_repository: PromptRepository,
    ) -> None:
        self._providers = providers
        self._agents = agents
        self.prompt_repository = prompt_repository
        self._execution_logs: list[AIExecutionLog] = []

    def select_provider(self, name: str | None = None) -> AIProvider:
        """Pick a provider by name, or the first registered one if `name` is omitted."""
        if name is not None:
            try:
                return self._providers[name]
            except KeyError as exc:
                raise ProviderNotAvailableError(name) from exc
        if not self._providers:
            raise NoProviderAvailableError()
        return next(iter(self._providers.values()))

    def load_prompt(self, name: str, variables: dict[str, str], *, version: int | None = None) -> str:
        return self.prompt_repository.render(name, variables, version=version)

    async def execute_agent(self, agent_type: AgentType, context: AIContext) -> AgentResult:
        agent = self._agents.get(agent_type)
        if agent is None:
            raise AgentNotRegisteredError(agent_type)
        result = await agent.execute(context)
        self.register_execution(result)
        return result

    async def execute(self, agent_type: AgentType, context: AIContext) -> AgentResult:
        """Public entrypoint: run a single agent. Every AI call in the platform starts here."""
        return await self.execute_agent(agent_type, context)

    async def execute_pipeline(
        self, agent_types: list[AgentType], context: AIContext
    ) -> list[AgentResult]:
        """Run agents in sequence, feeding each successful payload into the next agent's memory."""
        results: list[AgentResult] = []
        current_context = context
        for agent_type in agent_types:
            result = await self.execute_agent(agent_type, current_context)
            results.append(result)
            if result.success and result.payload is not None:
                current_context = current_context.model_copy(
                    update={"memory": [*current_context.memory, result.payload]}
                )
        return results

    def register_execution(self, result: AgentResult) -> AIExecutionLog:
        log = AIExecutionLog(
            agent_name=result.agent_name,
            provider=result.provider,
            model=result.model,
            execution_time=result.execution_time,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            estimated_cost=result.estimated_cost,
            success=result.success,
        )
        self._execution_logs.append(log)
        return log

    def list_execution_logs(self) -> list[AIExecutionLog]:
        return list(self._execution_logs)
