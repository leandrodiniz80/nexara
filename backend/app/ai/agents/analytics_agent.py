from typing import Any, ClassVar

from app.ai.agents.agent_base import AgentBase
from app.ai.agents.enums import AgentType
from app.ai.schemas.ai_context import AIContext


class AnalyticsAgent(AgentBase):
    """Derives insights/trends across prospects and campaigns. Not implemented yet."""

    agent_type: ClassVar[AgentType] = AgentType.ANALYTICS
    name: ClassVar[str] = "analytics_agent"

    def validate(self, context: AIContext) -> None:
        raise NotImplementedError("AnalyticsAgent.validate() is not implemented yet.")

    def prepare_context(self, context: AIContext) -> dict[str, Any]:
        raise NotImplementedError("AnalyticsAgent.prepare_context() is not implemented yet.")

    async def run(self, prepared_context: dict[str, Any]) -> Any:
        raise NotImplementedError("AnalyticsAgent.run() is not implemented yet.")

    def post_process(self, raw_output: Any) -> dict[str, Any]:
        raise NotImplementedError("AnalyticsAgent.post_process() is not implemented yet.")
