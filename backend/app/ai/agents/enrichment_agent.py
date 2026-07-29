from typing import Any, ClassVar

from app.ai.agents.agent_base import AgentBase
from app.ai.agents.enums import AgentType
from app.ai.schemas.ai_context import AIContext


class EnrichmentAgent(AgentBase):
    """Fills gaps in Company/Contact data from external signals. Not implemented yet."""

    agent_type: ClassVar[AgentType] = AgentType.ENRICHMENT
    name: ClassVar[str] = "enrichment_agent"

    def validate(self, context: AIContext) -> None:
        raise NotImplementedError("EnrichmentAgent.validate() is not implemented yet.")

    def prepare_context(self, context: AIContext) -> dict[str, Any]:
        raise NotImplementedError("EnrichmentAgent.prepare_context() is not implemented yet.")

    async def run(self, prepared_context: dict[str, Any]) -> Any:
        raise NotImplementedError("EnrichmentAgent.run() is not implemented yet.")

    def post_process(self, raw_output: Any) -> dict[str, Any]:
        raise NotImplementedError("EnrichmentAgent.post_process() is not implemented yet.")
