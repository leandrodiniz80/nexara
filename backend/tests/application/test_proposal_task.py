import uuid

import pytest

from app.application.tasks.context.task_context import TaskContext
from app.application.tasks.exceptions.task_exceptions import TaskValidationError
from app.application.tasks.proposal_task import ProposalTask
from app.outreach.models.enums import MessageStatus
from app.outreach.services.outreach_engine_factory import build_default_outreach_engine


def test_validate_requires_prospect_id():
    task = ProposalTask(build_default_outreach_engine())

    with pytest.raises(TaskValidationError):
        task.validate(TaskContext(variables={"template_id": uuid.uuid4()}))


def test_validate_requires_template_id():
    task = ProposalTask(build_default_outreach_engine())

    with pytest.raises(TaskValidationError):
        task.validate(TaskContext(prospect_id=uuid.uuid4(), variables={}))


async def test_execute_generates_and_submits_an_asset_from_an_explicit_template():
    engine = build_default_outreach_engine()
    meeting_template = engine.template_repository.get_active_by_category("meeting")
    task = ProposalTask(engine)
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

    assert output["status"] == MessageStatus.PENDING_APPROVAL.value
    assert output["template_id"] == str(meeting_template.id)


async def test_rollback_is_a_documented_no_op():
    task = ProposalTask(build_default_outreach_engine())
    await task.rollback(TaskContext(prospect_id=uuid.uuid4()))
