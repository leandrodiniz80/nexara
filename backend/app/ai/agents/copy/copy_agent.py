from typing import Any, ClassVar

from app.ai.agents.agent_base import AgentBase
from app.ai.agents.copy.copy_context_builder import CopyContextBuilder
from app.ai.agents.copy.copy_prompt_builder import CopyPromptBuilder
from app.ai.agents.copy.copy_result_parser import CopyResultParser
from app.ai.agents.enums import AgentType
from app.ai.exceptions.agent_exceptions import AgentValidationError
from app.ai.prompts.prompt_repository import PromptRepository
from app.ai.providers.base.ai_provider import AIProvider
from app.ai.schemas.ai_context import AIContext
from app.outreach.models.enums import AssetType


class CopyAgent(AgentBase):
    """Drafts commercial copy — not "emails": it generates OutreachAssets (email,
    whatsapp, proposal, whatever AssetType names). Never talks to a Provider by name:
    it only calls `self.provider.generate()` through the abstract AIProvider interface
    injected by whoever constructed it (see copy_agent_factory.py / AIOrchestrator's
    own composition root), and it never sees which concrete AI vendor or model is
    behind that interface.

    No prompt text lives here — CopyPromptBuilder builds it. No parsing logic lives
    here — CopyResultParser handles it. This class only wires the four AgentBase hooks
    to those collaborators.
    """

    agent_type: ClassVar[AgentType] = AgentType.COPY
    name: ClassVar[str] = "copy_agent"

    def __init__(
        self,
        provider: AIProvider,
        prompt_repository: PromptRepository,
        *,
        context_builder: CopyContextBuilder | None = None,
        prompt_builder: CopyPromptBuilder | None = None,
        result_parser: CopyResultParser | None = None,
    ) -> None:
        super().__init__(provider, prompt_repository)
        self.context_builder = context_builder or CopyContextBuilder()
        self.prompt_builder = prompt_builder or CopyPromptBuilder()
        self.result_parser = result_parser or CopyResultParser()

    def validate(self, context: AIContext) -> None:
        if context.company is None:
            raise AgentValidationError(
                "CopyAgent requires AIContext.company to generate copy about a company."
            )
        asset_type_value = context.variables.get("asset_type")
        if not asset_type_value:
            raise AgentValidationError("CopyAgent requires context.variables['asset_type'].")
        try:
            AssetType(asset_type_value)
        except ValueError as exc:
            raise AgentValidationError(f"Unknown asset_type '{asset_type_value}'.") from exc

    def prepare_context(self, context: AIContext) -> dict[str, Any]:
        copy_context = self.context_builder.build(context)
        prompt = self.prompt_builder.build(copy_context)
        return {"prompt": prompt, "context": copy_context}

    async def run(self, prepared_context: dict[str, Any]) -> Any:
        response = await self.provider.generate(prepared_context["prompt"])
        return {"response": response, "context": prepared_context["context"]}

    def post_process(self, raw_output: Any) -> dict[str, Any]:
        rendered = self.result_parser.parse(raw_output["response"], raw_output["context"])
        return rendered.model_dump()
