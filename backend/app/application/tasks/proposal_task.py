from typing import Any, ClassVar

from app.application.tasks.base.application_task import ApplicationTask, TaskType
from app.application.tasks.context.task_context import TaskContext
from app.application.tasks.exceptions.task_exceptions import TaskValidationError
from app.outreach.engine.outreach_engine import OutreachEngine
from app.outreach.schemas.generation_request import GenerationRequest


class ProposalTask(ApplicationTask):
    """ProposalTask -> OutreachEngine -> TaskResult.

    Template-based, not AI-based: generates a PROPOSAL-type asset from a stored
    AssetTemplate the caller already knows the id of. No default "proposal" category
    template exists among Outreach's three mocked templates (first_contact/
    follow_up/meeting), and this task doesn't register one itself — Outreach is
    frozen this sprint, and inventing a real proposal template's copy is a business
    decision this Task layer has no business making. `template_id` is required.
    """

    task_type: ClassVar[TaskType] = TaskType.PROPOSAL
    name: ClassVar[str] = "proposal_task"

    def __init__(self, outreach_engine: OutreachEngine) -> None:
        self.outreach_engine = outreach_engine

    def validate(self, context: TaskContext) -> None:
        if context.prospect_id is None:
            raise TaskValidationError("ProposalTask requires TaskContext.prospect_id.")
        if "template_id" not in context.variables:
            raise TaskValidationError(
                "ProposalTask requires TaskContext.variables['template_id'] "
                "(no default proposal template is registered)."
            )

    async def execute(self, context: TaskContext) -> dict[str, Any]:
        request = GenerationRequest(
            prospect_id=context.prospect_id,
            template_id=context.variables["template_id"],
            variables={k: v for k, v in context.variables.items() if k != "template_id"},
        )
        asset = self.outreach_engine.generate_message(request)
        asset = self.outreach_engine.submit_for_approval(asset)
        return asset.model_dump(mode="json")

    async def rollback(self, context: TaskContext) -> None:
        """OutreachAssetRepository (frozen) has no delete() — best-effort no-op."""
