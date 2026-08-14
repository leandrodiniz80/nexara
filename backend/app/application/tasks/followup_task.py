from typing import Any, ClassVar

from app.application.tasks.base.application_task import ApplicationTask, TaskType
from app.application.tasks.context.task_context import TaskContext
from app.application.tasks.exceptions.task_exceptions import (
    TaskExecutionError,
    TaskValidationError,
)
from app.outreach.engine.outreach_engine import OutreachEngine
from app.outreach.schemas.generation_request import GenerationRequest

_DEFAULT_CATEGORY = "follow_up"


class FollowupTask(ApplicationTask):
    """FollowupTask -> OutreachEngine -> TaskResult.

    Template-based, defaults to Outreach's own "follow_up" mocked template category
    when the caller doesn't specify a `template_id` — the one task in this sprint
    that works out of the box with no extra wiring, since that template already
    exists in any OutreachEngine built by build_default_outreach_engine().
    """

    task_type: ClassVar[TaskType] = TaskType.FOLLOWUP
    name: ClassVar[str] = "followup_task"

    def __init__(self, outreach_engine: OutreachEngine) -> None:
        self.outreach_engine = outreach_engine

    def validate(self, context: TaskContext) -> None:
        if context.prospect_id is None:
            raise TaskValidationError("FollowupTask requires TaskContext.prospect_id.")

    async def execute(self, context: TaskContext) -> dict[str, Any]:
        template_id = context.variables.get("template_id")
        if template_id is None:
            template = self.outreach_engine.template_repository.get_active_by_category(
                _DEFAULT_CATEGORY
            )
            if template is None:
                raise TaskExecutionError(
                    f"No active '{_DEFAULT_CATEGORY}' template registered."
                )
            template_id = template.id

        request = GenerationRequest(
            prospect_id=context.prospect_id,
            template_id=template_id,
            variables={k: v for k, v in context.variables.items() if k != "template_id"},
        )
        asset = self.outreach_engine.generate_message(request)
        asset = self.outreach_engine.submit_for_approval(asset)
        return asset.model_dump(mode="json")

    async def rollback(self, context: TaskContext) -> None:
        """OutreachAssetRepository (frozen) has no delete() — best-effort no-op."""
