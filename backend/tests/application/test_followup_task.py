import uuid

import pytest

from app.application.tasks.context.task_context import TaskContext
from app.application.tasks.exceptions.task_exceptions import (
    TaskExecutionError,
    TaskValidationError,
)
from app.application.tasks.followup_task import FollowupTask
from app.outreach.approval.approval_service import ApprovalService
from app.outreach.engine.outreach_engine import OutreachEngine
from app.outreach.models.enums import MessageStatus
from app.outreach.render.asset_renderer import AssetRenderer
from app.outreach.repositories.outreach_asset_repository import OutreachAssetRepository
from app.outreach.repositories.template_repository import TemplateRepository
from app.outreach.services.outreach_engine_factory import build_default_outreach_engine
from app.outreach.validators.message_validator import MessageValidator


def _empty_outreach_engine() -> OutreachEngine:
    return OutreachEngine(
        template_repository=TemplateRepository(),
        asset_repository=OutreachAssetRepository(),
        generator=AssetRenderer(),
        validator=MessageValidator(),
        approval_service=ApprovalService(),
    )


def test_validate_requires_prospect_id():
    task = FollowupTask(build_default_outreach_engine())

    with pytest.raises(TaskValidationError):
        task.validate(TaskContext())


async def test_execute_uses_the_default_follow_up_template_when_none_given():
    task = FollowupTask(build_default_outreach_engine())
    context = TaskContext(
        prospect_id=uuid.uuid4(),
        variables={"contact_name": "João", "company": "Agência XYZ"},
    )

    output = await task.execute(context)

    assert output["status"] == MessageStatus.PENDING_APPROVAL.value
    assert "João" in output["content"]


async def test_execute_uses_an_explicit_template_id_when_given():
    engine = build_default_outreach_engine()
    meeting_template = engine.template_repository.get_active_by_category("meeting")
    task = FollowupTask(engine)
    context = TaskContext(
        prospect_id=uuid.uuid4(),
        variables={
            "template_id": meeting_template.id,
            "contact_name": "João",
            "company": "Agência XYZ",
            "city": "Goiânia",
        },
    )

    output = await task.execute(context)

    assert output["template_id"] == str(meeting_template.id)


async def test_execute_raises_when_no_default_category_is_registered():
    task = FollowupTask(_empty_outreach_engine())
    context = TaskContext(prospect_id=uuid.uuid4(), variables={})

    with pytest.raises(TaskExecutionError):
        await task.execute(context)


async def test_rollback_is_a_documented_no_op():
    task = FollowupTask(build_default_outreach_engine())
    await task.rollback(TaskContext(prospect_id=uuid.uuid4()))
