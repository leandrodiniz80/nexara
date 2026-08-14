from typing import Any, ClassVar

from app.ai.agents.copy.copy_result_parser import CopyResultParser
from app.ai.agents.enums import AgentType
from app.ai.orchestrator.ai_orchestrator import AIOrchestrator
from app.ai.schemas.ai_context import AIContext
from app.application.tasks.base.application_task import ApplicationTask, TaskType
from app.application.tasks.context.task_context import TaskContext
from app.application.tasks.exceptions.task_exceptions import (
    TaskExecutionError,
    TaskValidationError,
)
from app.outreach.engine.outreach_engine import OutreachEngine
from app.outreach.models.asset_template import AssetTemplate
from app.outreach.models.enums import AssetType, Channel
from app.outreach.repositories.template_repository import TemplateRepository

_AI_GENERATED_CATEGORY_PREFIX = "ai_generated"
# company/prospect/mission become dedicated AIContext fields, not AIContext.variables
# entries — everything else (including "asset_type", which CopyContextBuilder itself
# requires to find in variables) passes through unchanged.
_TASK_CONTEXT_ONLY_KEYS = {"company", "prospect", "mission"}


def ai_generated_category(channel: Channel) -> str:
    return f"{_AI_GENERATED_CATEGORY_PREFIX}_{channel.value}"


def register_ai_generated_templates(template_repository: TemplateRepository) -> None:
    """CopyTask needs a `template_id` to satisfy OutreachAsset's (frozen) schema even
    though AI-generated content isn't rendered from a stored template. These are
    trivial, placeholder-free templates — one per Channel — that exist only to carry
    a valid template reference and the right per-channel length limit through
    MessageValidator; their `body` is never actually used as content. Idempotent, so
    it's safe to call every time a CopyTask is built.
    """
    for channel in Channel:
        category = ai_generated_category(channel)
        if template_repository.get_active_by_category(category) is not None:
            continue
        template_repository.add(
            AssetTemplate(
                name=f"AI Generated ({channel.value})",
                category=category,
                channel=channel,
                subject=None,
                body="Conteúdo gerado por IA — ver OutreachAsset.content.",
                variables=[],
            )
        )


class CopyTask(ApplicationTask):
    """CopyTask -> CopyAgent -> OutreachEngine -> TaskResult.

    Calls AIOrchestrator.execute_agent(AgentType.COPY, ...) to get AI-generated copy,
    then hands the result to OutreachEngine to persist it as an OutreachAsset and run
    it through the exact same validate()/submit_for_approval() pipeline a
    template-rendered asset goes through — no separate approval path for AI content.
    """

    task_type: ClassVar[TaskType] = TaskType.COPY
    name: ClassVar[str] = "copy_task"

    def __init__(self, ai_orchestrator: AIOrchestrator, outreach_engine: OutreachEngine) -> None:
        self.ai_orchestrator = ai_orchestrator
        self.outreach_engine = outreach_engine
        register_ai_generated_templates(self.outreach_engine.template_repository)

    def validate(self, context: TaskContext) -> None:
        if context.prospect_id is None:
            raise TaskValidationError("CopyTask requires TaskContext.prospect_id.")
        if "company" not in context.variables:
            raise TaskValidationError(
                "CopyTask requires TaskContext.variables['company'] (a CompanyRead)."
            )
        if "asset_type" not in context.variables:
            raise TaskValidationError("CopyTask requires TaskContext.variables['asset_type'].")
        try:
            AssetType(context.variables["asset_type"])
        except ValueError as exc:
            raise TaskValidationError(
                f"Unknown asset_type '{context.variables['asset_type']}'."
            ) from exc

    async def execute(self, context: TaskContext) -> dict[str, Any]:
        try:
            asset_type = AssetType(context.variables["asset_type"])
            channel = Channel(asset_type.value)
        except ValueError as exc:
            raise TaskExecutionError(
                f"CopyTask only supports channel-based asset types today, got "
                f"'{context.variables['asset_type']}'."
            ) from exc

        ai_context = AIContext(
            company=context.variables.get("company"),
            prospect=context.variables.get("prospect"),
            mission=context.variables.get("mission"),
            variables={
                k: v for k, v in context.variables.items() if k not in _TASK_CONTEXT_ONLY_KEYS
            },
        )
        agent_result = await self.ai_orchestrator.execute_agent(AgentType.COPY, ai_context)
        if not agent_result.success:
            raise TaskExecutionError(f"CopyAgent failed: {'; '.join(agent_result.logs)}")

        rendered = CopyResultParser.from_agent_payload(agent_result.payload)

        template = self.outreach_engine.template_repository.get_active_by_category(
            ai_generated_category(channel)
        )
        if template is None:
            raise TaskExecutionError(f"No AI-generated template registered for '{channel.value}'.")

        asset = self.outreach_engine.asset_repository.create(
            prospect_id=context.prospect_id,
            template_id=template.id,
            asset_type=asset_type,
            channel=channel,
            title=rendered.title,
            content=rendered.content,
            metadata=rendered.metadata,
            generated_by="copy_agent",
        )
        asset = self.outreach_engine.submit_for_approval(asset)
        return asset.model_dump(mode="json")

    async def rollback(self, context: TaskContext) -> None:
        """OutreachAssetRepository (frozen) has no delete() — the asset this task
        created stays in DRAFT/rejected state in memory rather than being removed.
        Best-effort no-op, documented rather than faked."""
