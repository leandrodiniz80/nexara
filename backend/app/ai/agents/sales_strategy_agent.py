from typing import Any, ClassVar

from app.ai.agents.agent_base import AgentBase
from app.ai.agents.enums import AgentType
from app.ai.schemas.ai_context import AIContext


class SalesStrategyAgent(AgentBase):
    """Suggests next best action / approach strategy for a Prospect. Not implemented yet."""

    agent_type: ClassVar[AgentType] = AgentType.SALES_STRATEGY
    name: ClassVar[str] = "sales_strategy_agent"

    def validate(self, context: AIContext) -> None:
        raise NotImplementedError("SalesStrategyAgent.validate() is not implemented yet.")

    def prepare_context(self, context: AIContext) -> dict[str, Any]:
        raise NotImplementedError("SalesStrategyAgent.prepare_context() is not implemented yet.")

    async def run(self, prepared_context: dict[str, Any]) -> Any:
        raise NotImplementedError("SalesStrategyAgent.run() is not implemented yet.")

    def post_process(self, raw_output: Any) -> dict[str, Any]:
        raise NotImplementedError("SalesStrategyAgent.post_process() is not implemented yet.")
