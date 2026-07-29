from typing import Any, ClassVar

from app.ai.agents.agent_base import AgentBase
from app.ai.agents.enums import AgentType
from app.ai.schemas.ai_context import AIContext


class CopyAgent(AgentBase):
    """Drafts outreach copy (email/message content). Not implemented yet."""

    agent_type: ClassVar[AgentType] = AgentType.COPY
    name: ClassVar[str] = "copy_agent"

    def validate(self, context: AIContext) -> None:
        raise NotImplementedError("CopyAgent.validate() is not implemented yet.")

    def prepare_context(self, context: AIContext) -> dict[str, Any]:
        raise NotImplementedError("CopyAgent.prepare_context() is not implemented yet.")

    async def run(self, prepared_context: dict[str, Any]) -> Any:
        raise NotImplementedError("CopyAgent.run() is not implemented yet.")

    def post_process(self, raw_output: Any) -> dict[str, Any]:
        raise NotImplementedError("CopyAgent.post_process() is not implemented yet.")
