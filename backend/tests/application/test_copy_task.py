import uuid
from datetime import datetime, timezone

import pytest

from app.ai.services.ai_orchestrator_factory import build_default_orchestrator
from app.application.tasks.context.task_context import TaskContext
from app.application.tasks.copy_task import CopyTask, ai_generated_category
from app.application.tasks.exceptions.task_exceptions import (
    TaskExecutionError,
    TaskValidationError,
)
from app.outreach.models.enums import Channel, MessageStatus
from app.outreach.services.outreach_engine_factory import build_default_outreach_engine
from app.schemas.prospecting.company import CompanyRead


def _company(**overrides) -> CompanyRead:
    defaults = dict(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        legal_name="Agência XYZ Ltda",
        trade_name="Agência XYZ",
        cnpj="12345678000199",
        segment="Publicidade",
        city="Goiânia",
        state="GO",
    )
    defaults.update(overrides)
    return CompanyRead(**defaults)


def _build_task() -> CopyTask:
    return CopyTask(build_default_orchestrator(), build_default_outreach_engine())


def _worked_example_context() -> TaskContext:
    return TaskContext(
        prospect_id=uuid.uuid4(),
        variables={
            "company": _company(),
            "asset_type": "email",
            "tone": "consultivo",
            "contact_name": "João",
            "objective": "Conseguir reunião",
        },
    )


def test_validate_requires_prospect_id():
    task = _build_task()
    context = TaskContext(variables={"company": _company(), "asset_type": "email"})

    with pytest.raises(TaskValidationError):
        task.validate(context)


def test_validate_requires_company():
    task = _build_task()
    context = TaskContext(prospect_id=uuid.uuid4(), variables={"asset_type": "email"})

    with pytest.raises(TaskValidationError):
        task.validate(context)


def test_validate_requires_asset_type():
    task = _build_task()
    context = TaskContext(prospect_id=uuid.uuid4(), variables={"company": _company()})

    with pytest.raises(TaskValidationError):
        task.validate(context)


def test_construction_registers_ai_generated_templates():
    outreach_engine = build_default_outreach_engine()
    CopyTask(build_default_orchestrator(), outreach_engine)

    for channel in Channel:
        template = outreach_engine.template_repository.get_active_by_category(
            ai_generated_category(channel)
        )
        assert template is not None
        assert template.variables == []


async def test_full_worked_example_produces_a_pending_approval_outreach_asset():
    """CopyTask -> CopyAgent -> OutreachEngine -> TaskResult, exactly as specified:
    Empresa=Agência XYZ, Cidade=Goiânia, Contato=João, Asset=EMAIL, Tom=Consultivo."""
    task = _build_task()

    output = await task.execute(_worked_example_context())

    assert output["status"] == MessageStatus.PENDING_APPROVAL.value
    assert output["asset_type"] == "email"
    assert output["channel"] == "email"
    assert output["generated_by"] == "copy_agent"
    assert output["content"]
    assert output["metadata"]["tone"] == "consultivo"


async def test_execute_raises_for_non_channel_asset_types():
    task = _build_task()
    context = _worked_example_context()
    context.variables["asset_type"] = "video"

    with pytest.raises(TaskExecutionError):
        await task.execute(context)


async def test_execute_raises_task_execution_error_for_unknown_asset_type_even_without_validate():
    """Defensive: execute() itself must never leak a raw ValueError, even if a caller
    skipped validate() (matching TemplateRenderer's own defensive re-check in
    Outreach — the same "validate() should have caught this, but don't trust it"
    idiom)."""
    task = _build_task()
    context = TaskContext(
        prospect_id=uuid.uuid4(),
        variables={"company": _company(), "asset_type": "carrier_pigeon"},
    )

    with pytest.raises(TaskExecutionError):
        await task.execute(context)


async def test_execute_raises_when_copy_agent_fails():
    """CopyAgent.validate() itself requires AIContext.company — leaving it out of
    TaskContext.variables (while still passing CopyTask's own validate(), which only
    checks the key is present) makes the underlying agent fail, not CopyTask."""
    task = _build_task()
    context = TaskContext(
        prospect_id=uuid.uuid4(),
        variables={"company": None, "asset_type": "email"},
    )

    with pytest.raises(TaskExecutionError):
        await task.execute(context)


async def test_rollback_is_a_documented_no_op():
    task = _build_task()
    await task.rollback(_worked_example_context())
