import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.application.tasks.context.task_context import TaskContext
from app.automation.engine.automation_engine import AutomationEngine
from app.automation.exceptions.automation_exceptions import AutomationNotTriggeredError
from app.automation.models.automation import Automation
from app.automation.models.automation_schedule import AutomationSchedule
from app.automation.models.automation_trigger import AutomationTrigger
from app.automation.models.enums import AutomationStatus, AutomationTriggerType
from app.automation.registry.automation_registry import AutomationRegistry
from app.automation.repositories.automation_repository import AutomationRepository
from app.workflows.models.enums import WorkflowStatus
from app.workflows.models.workflow_execution import WorkflowExecution
from app.workflows.models.workflow_result import WorkflowResult
from app.workflows.schemas.workflow_request import WorkflowRequest
from app.workflows.schemas.workflow_response import WorkflowResponse


class _FakeWorkflowEngine:
    """Satisfies exactly the shape AutomationEngine relies on
    (`async def execute(request: WorkflowRequest) -> WorkflowResponse`) — not a
    real WorkflowEngine, so these tests stay isolated from the Task layer beneath
    it entirely."""

    def __init__(self, *, success: bool = True) -> None:
        self.success = success
        self.calls: list[WorkflowRequest] = []

    async def execute(self, request: WorkflowRequest) -> WorkflowResponse:
        self.calls.append(request)
        execution = WorkflowExecution(
            workflow_id=uuid.uuid4(),
            status=WorkflowStatus.COMPLETED if self.success else WorkflowStatus.PAUSED,
        )
        result = WorkflowResult(
            success=self.success,
            execution=execution,
            errors=[] if self.success else ["a step failed"],
            duration=0.01,
        )
        return WorkflowResponse(result=result)


def _automation(**overrides) -> Automation:
    defaults = dict(
        name="Test Automation",
        workflow_name="Test Workflow",
        trigger=AutomationTrigger(type=AutomationTriggerType.MANUAL),
    )
    defaults.update(overrides)
    return Automation(**defaults)


def _build_engine(automation: Automation, *, workflow_success: bool = True):
    registry = AutomationRegistry()
    registry.register(automation)
    workflow_engine = _FakeWorkflowEngine(success=workflow_success)
    engine = AutomationEngine(
        repository=AutomationRepository(),
        registry=registry,
        workflow_engine=workflow_engine,
    )
    return engine, workflow_engine


def _workflow_request() -> WorkflowRequest:
    return WorkflowRequest(workflow_name="ignored-by-automation-engine", context=TaskContext())


async def test_execute_manual_runs_the_workflow_and_uses_the_automations_own_workflow_name():
    automation = _automation()
    engine, fake = _build_engine(automation)

    response = await engine.execute_manual(automation.name, _workflow_request())

    assert response.workflow_result.success is True
    assert fake.calls[0].workflow_name == "Test Workflow"  # not "ignored-by-automation-engine"
    assert response.execution.status == AutomationStatus.COMPLETED
    assert response.execution.automation_id == automation.id
    expected_workflow_execution_id = response.workflow_result.execution.execution_id
    assert response.execution.workflow_execution_id == expected_workflow_execution_id


async def test_execute_manual_on_a_disabled_automation_raises():
    automation = _automation(enabled=False)
    engine, _ = _build_engine(automation)

    with pytest.raises(AutomationNotTriggeredError):
        await engine.execute_manual(automation.name, _workflow_request())


async def test_execute_records_failed_status_when_workflow_result_is_unsuccessful():
    automation = _automation()
    engine, _ = _build_engine(automation, workflow_success=False)

    response = await engine.execute_manual(automation.name, _workflow_request())

    assert response.execution.status == AutomationStatus.FAILED
    assert response.execution.errors == ["a step failed"]


async def test_execute_scheduled_fires_when_due_and_stamps_last_execution():
    now = datetime.now(timezone.utc)
    automation = _automation(
        trigger=AutomationTrigger(type=AutomationTriggerType.SCHEDULED),
        schedule=AutomationSchedule(
            cron_expression="0 8 * * *", next_execution=now - timedelta(minutes=1)
        ),
    )
    engine, _ = _build_engine(automation)

    response = await engine.execute_scheduled(automation.name, _workflow_request(), now=now)

    assert response.execution.status == AutomationStatus.COMPLETED
    assert automation.schedule.last_execution == now


async def test_execute_scheduled_raises_when_not_yet_due():
    now = datetime.now(timezone.utc)
    automation = _automation(
        trigger=AutomationTrigger(type=AutomationTriggerType.SCHEDULED),
        schedule=AutomationSchedule(
            cron_expression="0 8 * * *", next_execution=now + timedelta(hours=1)
        ),
    )
    engine, _ = _build_engine(automation)

    with pytest.raises(AutomationNotTriggeredError):
        await engine.execute_scheduled(automation.name, _workflow_request(), now=now)


async def test_execute_event_fires_for_a_matching_event_name():
    automation = _automation(
        trigger=AutomationTrigger(
            type=AutomationTriggerType.EVENT, event_name="prospect_qualified"
        )
    )
    engine, _ = _build_engine(automation)

    response = await engine.execute_event(
        automation.name, _workflow_request(), event_name="prospect_qualified"
    )

    assert response.execution.status == AutomationStatus.COMPLETED


async def test_execute_event_raises_for_a_non_matching_event_name():
    automation = _automation(
        trigger=AutomationTrigger(
            type=AutomationTriggerType.EVENT, event_name="prospect_qualified"
        )
    )
    engine, _ = _build_engine(automation)

    with pytest.raises(AutomationNotTriggeredError):
        await engine.execute_event(automation.name, _workflow_request(), event_name="other_event")


async def test_execute_condition_fires_only_when_condition_met():
    automation = _automation(trigger=AutomationTrigger(type=AutomationTriggerType.CONDITION))
    engine, _ = _build_engine(automation)

    response = await engine.execute_condition(
        automation.name, _workflow_request(), condition_met=True
    )

    assert response.execution.status == AutomationStatus.COMPLETED

    with pytest.raises(AutomationNotTriggeredError):
        await engine.execute_condition(automation.name, _workflow_request(), condition_met=False)


def test_enable_and_disable_go_through_the_registry():
    automation = _automation(enabled=False)
    engine, _ = _build_engine(automation)

    enabled = engine.enable(automation.name)
    assert enabled.enabled is True

    disabled = engine.disable(automation.name)
    assert disabled.enabled is False


async def test_trigger_never_executes_a_workflow_directly():
    """ManualTrigger/ScheduledTrigger/EventTrigger/ConditionTrigger are pure
    predicates — none of them import WorkflowEngine or anything execution-shaped."""
    import app.automation.triggers.condition_trigger as condition_trigger
    import app.automation.triggers.event_trigger as event_trigger
    import app.automation.triggers.manual_trigger as manual_trigger
    import app.automation.triggers.scheduled_trigger as scheduled_trigger

    for module in (manual_trigger, scheduled_trigger, event_trigger, condition_trigger):
        with open(module.__file__, encoding="utf-8") as source_file:
            source = source_file.read()
        assert "WorkflowEngine" not in source
        assert "workflow_engine" not in source
