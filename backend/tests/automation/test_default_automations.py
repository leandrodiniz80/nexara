import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.application.tasks.context.task_context import TaskContext
from app.automation.exceptions.automation_exceptions import AutomationNotTriggeredError
from app.automation.models.enums import AutomationStatus, AutomationTriggerType
from app.automation.services.automation_engine_factory import (
    build_daily_prospecting_automation,
    build_default_automation_engine,
    build_default_automations,
    build_proposal_after_qualification_automation,
)
from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.schemas.prospecting.company import CompanyRead
from app.workflows.schemas.workflow_request import WorkflowRequest


def test_daily_prospecting_is_scheduled_for_the_prospecting_workflow():
    automation = build_daily_prospecting_automation()

    assert automation.name == "Daily Prospecting"
    assert automation.workflow_name == "Prospecting Workflow"
    assert automation.trigger.type == AutomationTriggerType.SCHEDULED
    assert automation.schedule is not None
    assert automation.enabled is True


def test_proposal_after_qualification_is_an_event_trigger_for_the_proposal_workflow():
    automation = build_proposal_after_qualification_automation()

    assert automation.name == "Proposal After Qualification"
    assert automation.workflow_name == "Proposal Workflow"
    assert automation.trigger.type == AutomationTriggerType.EVENT
    assert automation.trigger.event_name == "prospect_qualified"


def test_build_default_automations_returns_both():
    automations = build_default_automations()

    assert {a.name for a in automations} == {"Daily Prospecting", "Proposal After Qualification"}


def test_build_default_automations_is_deterministic():
    first = build_default_automations()
    second = build_default_automations()

    assert [a.name for a in first] == [a.name for a in second]
    assert [a.workflow_name for a in first] == [a.workflow_name for a in second]


def test_build_default_automation_engine_registers_both_by_default():
    engine = build_default_automation_engine()

    names = {a.name for a in engine.registry.list()}
    assert names == {"Daily Prospecting", "Proposal After Qualification"}


def _company() -> CompanyRead:
    now = datetime.now(timezone.utc)
    return CompanyRead(
        id=uuid.uuid4(),
        created_at=now,
        updated_at=now,
        legal_name="Agência XYZ Ltda",
        trade_name="Agência XYZ",
        cnpj="12345678000199",
        segment="Publicidade",
        city="Goiânia",
        state="GO",
    )


async def test_daily_prospecting_runs_end_to_end_via_execute_scheduled():
    """Uses the real WorkflowEngine (and, underneath it, the real
    ResearchTask/QualificationTask/CopyTask) — only the Providers beneath those are
    Mocks. AutomationEngine itself never touched any of that directly."""
    engine = build_default_automation_engine()
    automation = engine.registry.get("Daily Prospecting")
    now = datetime.now(timezone.utc)
    automation.schedule.next_execution = now - timedelta(minutes=1)

    workflow_request = WorkflowRequest(
        workflow_name="Prospecting Workflow",
        context=TaskContext(
            mission_id=uuid.uuid4(),
            prospect_id=uuid.uuid4(),
            variables={
                "strategy": "city",
                "query": {"city": "Goiânia"},
                "profile": CommercialProfile(segment="retail", company_size="small"),
                "company": _company(),
                "asset_type": "email",
            },
        ),
    )

    response = await engine.execute_scheduled("Daily Prospecting", workflow_request, now=now)

    assert response.execution.status in {AutomationStatus.COMPLETED, AutomationStatus.FAILED}
    assert automation.schedule.last_execution == now


async def test_daily_prospecting_does_not_fire_before_its_next_execution():
    engine = build_default_automation_engine()
    automation = engine.registry.get("Daily Prospecting")
    now = datetime.now(timezone.utc)
    automation.schedule.next_execution = now + timedelta(hours=1)

    with pytest.raises(AutomationNotTriggeredError):
        await engine.execute_scheduled(
            "Daily Prospecting",
            WorkflowRequest(workflow_name="Prospecting Workflow", context=TaskContext()),
            now=now,
        )
