from typing import Any

from pydantic import BaseModel, Field

from app.ai.exceptions.agent_exceptions import AgentValidationError
from app.ai.schemas.ai_context import AIContext
from app.outreach.models.enums import AssetType, Channel
from app.schemas.mission.mission import MissionRead
from app.schemas.prospecting.company import CompanyRead
from app.schemas.prospecting.prospect import ProspectRead

_CONTROL_KEYS = {"asset_type", "channel", "communication_style", "tone", "language"}


class CopyContext(BaseModel):
    """Everything CopyPromptBuilder needs to assemble a prompt — the CopyAgent-shaped
    view of the generic AIContext. Built once per execution by CopyContextBuilder so
    neither the prompt builder nor the agent itself has to reach into AIContext's
    generic `variables: dict[str, str]` bag directly.
    """

    company: CompanyRead | None = None
    prospect: ProspectRead | None = None
    mission: MissionRead | None = None
    commercial_profile: dict[str, Any] | None = None
    commercial_score: float | None = None
    recommendations: list[str] = Field(default_factory=list)
    asset_type: AssetType
    channel: Channel | None = None
    communication_style: str | None = None
    tone: str | None = None
    language: str = "pt-BR"
    variables: dict[str, Any] = Field(default_factory=dict)


class CopyContextBuilder:
    """Turns an AIContext into a CopyContext.

    `commercial_profile`/`commercial_score`/`recommendations` don't exist as AIContext
    fields — they're read out of `AIContext.memory`, the list where AIOrchestrator's
    execute_pipeline() stashes each prior agent's payload. This is how a future
    SalesStrategyAgent's output reaches CopyAgent without CopyAgent (or anything in
    app/ai) importing app.sales_intelligence directly: memory entries are opaque dicts.
    """

    def build(self, context: AIContext) -> CopyContext:
        asset_type_value = context.variables.get("asset_type")
        if not asset_type_value:
            raise AgentValidationError("CopyAgent requires context.variables['asset_type'].")
        try:
            asset_type = AssetType(asset_type_value)
        except ValueError as exc:
            raise AgentValidationError(f"Unknown asset_type '{asset_type_value}'.") from exc

        channel_value = context.variables.get("channel")
        channel = Channel(channel_value) if channel_value else None

        variables = {
            key: value for key, value in context.variables.items() if key not in _CONTROL_KEYS
        }
        if "contact_name" not in variables and context.contact is not None:
            variables["contact_name"] = context.contact.full_name

        return CopyContext(
            company=context.company,
            prospect=context.prospect,
            mission=context.mission,
            commercial_profile=self._from_memory(context.memory, "commercial_profile"),
            commercial_score=self._from_memory(context.memory, "commercial_score"),
            recommendations=self._from_memory(context.memory, "recommendations") or [],
            asset_type=asset_type,
            channel=channel,
            communication_style=context.variables.get("communication_style"),
            tone=context.variables.get("tone"),
            language=context.variables.get("language", "pt-BR"),
            variables=variables,
        )

    @staticmethod
    def _from_memory(memory: list[Any], key: str) -> Any | None:
        for entry in reversed(memory):
            if isinstance(entry, dict) and key in entry:
                return entry[key]
        return None
