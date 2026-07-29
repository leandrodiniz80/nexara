from typing import Any, ClassVar

from app.ai.agents.agent_base import AgentBase
from app.ai.agents.enums import AgentType
from app.ai.schemas.ai_context import AIContext


class ResearchAgent(AgentBase):
    """Gathers/consolidates open information about a Company/Prospect. Not implemented yet."""

    agent_type: ClassVar[AgentType] = AgentType.RESEARCH
    name: ClassVar[str] = "research_agent"

    def validate(self, context: AIContext) -> None:
        raise NotImplementedError("ResearchAgent.validate() is not implemented yet.")

    def prepare_context(self, context: AIContext) -> dict[str, Any]:
        raise NotImplementedError("ResearchAgent.prepare_context() is not implemented yet.")

    async def run(self, prepared_context: dict[str, Any]) -> Any:
        raise NotImplementedError("ResearchAgent.run() is not implemented yet.")

    def post_process(self, raw_output: Any) -> dict[str, Any]:
        raise NotImplementedError("ResearchAgent.post_process() is not implemented yet.")
