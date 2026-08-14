from datetime import datetime, timezone

from app.automation.exceptions.automation_exceptions import AutomationNotTriggeredError
from app.automation.models.automation import Automation
from app.automation.models.automation_execution import AutomationExecution
from app.automation.models.enums import AutomationStatus
from app.automation.registry.automation_registry import AutomationRegistry
from app.automation.repositories.automation_repository import AutomationRepository
from app.automation.schemas.automation_request import AutomationRequest
from app.automation.schemas.automation_response import AutomationResponse
from app.automation.triggers.condition_trigger import ConditionTrigger
from app.automation.triggers.event_trigger import EventTrigger
from app.automation.triggers.manual_trigger import ManualTrigger
from app.automation.triggers.scheduled_trigger import ScheduledTrigger
from app.workflows.engine.workflow_engine import WorkflowEngine
from app.workflows.schemas.workflow_request import WorkflowRequest


class AutomationEngine:
    """Fires Workflows automatically — nothing else. It never constructs a Task,
    never imports TaskExecutor/ApplicationTask/MissionEngine/ResearchEngine/
    OutreachEngine/AIOrchestrator/CopyAgent/SalesIntelligence; the only thing it
    calls to actually do work is `WorkflowEngine.execute()`. Every execute_*()
    method asks its matching Trigger "should this fire?" first — the Trigger
    decides, this engine (and only this engine) executes.
    """

    def __init__(
        self,
        repository: AutomationRepository,
        registry: AutomationRegistry,
        workflow_engine: WorkflowEngine,
    ) -> None:
        self.repository = repository
        self.registry = registry
        self.workflow_engine = workflow_engine

    async def execute(self, request: AutomationRequest) -> AutomationResponse:
        """The shared, unconditional path every execute_*() method below delegates
        to once its own Trigger has already said yes — looks up the Automation and
        always runs its Workflow. No trigger check happens here; that is each
        specific method's own responsibility before it ever calls this.
        """
        automation = self.registry.get(request.automation_name)
        execution = AutomationExecution(
            automation_id=automation.id, status=AutomationStatus.RUNNING
        )
        self.repository.save_execution(execution)

        workflow_request = WorkflowRequest(
            workflow_name=automation.workflow_name,
            context=request.workflow_request.context,
        )
        workflow_response = await self.workflow_engine.execute(workflow_request)
        workflow_result = workflow_response.result

        execution.workflow_execution_id = workflow_result.execution.execution_id
        execution.warnings = list(workflow_result.warnings)
        execution.errors = list(workflow_result.errors)
        execution.status = (
            AutomationStatus.COMPLETED if workflow_result.success else AutomationStatus.FAILED
        )
        execution.finished_at = datetime.now(timezone.utc)
        self.repository.save_execution(execution)

        return AutomationResponse(execution=execution, workflow_result=workflow_result)

    async def execute_manual(
        self, automation_name: str, workflow_request: WorkflowRequest
    ) -> AutomationResponse:
        automation = self.registry.get(automation_name)
        if not ManualTrigger.should_fire(automation):
            raise AutomationNotTriggeredError(automation_name, "manual")
        return await self.execute(
            AutomationRequest(automation_name=automation_name, workflow_request=workflow_request)
        )

    async def execute_scheduled(
        self, automation_name: str, workflow_request: WorkflowRequest, *, now: datetime
    ) -> AutomationResponse:
        automation = self.registry.get(automation_name)
        if not ScheduledTrigger.should_fire(automation, now=now):
            raise AutomationNotTriggeredError(automation_name, "scheduled")
        response = await self.execute(
            AutomationRequest(automation_name=automation_name, workflow_request=workflow_request)
        )
        if automation.schedule is not None:
            automation.schedule.last_execution = now
        return response

    async def execute_event(
        self, automation_name: str, workflow_request: WorkflowRequest, *, event_name: str
    ) -> AutomationResponse:
        automation = self.registry.get(automation_name)
        if not EventTrigger.should_fire(automation, event_name=event_name):
            raise AutomationNotTriggeredError(automation_name, "event")
        return await self.execute(
            AutomationRequest(automation_name=automation_name, workflow_request=workflow_request)
        )

    async def execute_condition(
        self, automation_name: str, workflow_request: WorkflowRequest, *, condition_met: bool
    ) -> AutomationResponse:
        automation = self.registry.get(automation_name)
        if not ConditionTrigger.should_fire(automation, condition_met=condition_met):
            raise AutomationNotTriggeredError(automation_name, "condition")
        return await self.execute(
            AutomationRequest(automation_name=automation_name, workflow_request=workflow_request)
        )

    def enable(self, automation_name: str) -> Automation:
        return self.registry.enable(automation_name)

    def disable(self, automation_name: str) -> Automation:
        return self.registry.disable(automation_name)
