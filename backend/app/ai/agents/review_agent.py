from typing import Any, ClassVar

from app.ai.agents.agent_base import AgentBase
from app.ai.agents.enums import AgentType
from app.ai.schemas.ai_context import AIContext


class ReviewAgent(AgentBase):
    """Reviews/critiques content produced by other agents before it goes out. Not implemented yet."""

    agent_type: ClassVar[AgentType] = AgentType.REVIEW
    name: ClassVar[str] = "review_agent"

    def validate(self, context: AIContext) -> None:
        raise NotImplementedError("ReviewAgent.validate() is not implemented yet.")

    def prepare_context(self, context: AIContext) -> dict[str, Any]:
        raise NotImplementedError("ReviewAgent.prepare_context() is not implemented yet.")

    async def run(self, prepared_context: dict[str, Any]) -> Any:
        raise NotImplementedError("ReviewAgent.run() is not implemented yet.")

    def post_process(self, raw_output: Any) -> dict[str, Any]:
        raise NotImplementedError("ReviewAgent.post_process() is not implemented yet.")
