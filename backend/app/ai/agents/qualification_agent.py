from typing import Any, ClassVar

from app.ai.agents.agent_base import AgentBase
from app.ai.agents.enums import AgentType
from app.ai.schemas.ai_context import AIContext


class QualificationAgent(AgentBase):
    """Assesses fit/readiness of a Prospect (feeds ProspectEngine.qualify()). Not implemented yet."""

    agent_type: ClassVar[AgentType] = AgentType.QUALIFICATION
    name: ClassVar[str] = "qualification_agent"

    def validate(self, context: AIContext) -> None:
        raise NotImplementedError("QualificationAgent.validate() is not implemented yet.")

    def prepare_context(self, context: AIContext) -> dict[str, Any]:
        raise NotImplementedError("QualificationAgent.prepare_context() is not implemented yet.")

    async def run(self, prepared_context: dict[str, Any]) -> Any:
        raise NotImplementedError("QualificationAgent.run() is not implemented yet.")

    def post_process(self, raw_output: Any) -> dict[str, Any]:
        raise NotImplementedError("QualificationAgent.post_process() is not implemented yet.")
