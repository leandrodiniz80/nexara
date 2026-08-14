from app.automation.engine.automation_engine import AutomationEngine
from app.automation.models.automation import Automation
from app.automation.models.automation_schedule import AutomationSchedule
from app.automation.models.automation_trigger import AutomationTrigger
from app.automation.models.enums import AutomationTriggerType
from app.automation.registry.automation_registry import AutomationRegistry
from app.automation.repositories.automation_repository import AutomationRepository
from app.workflows.engine.workflow_engine import WorkflowEngine
from app.workflows.services.workflow_engine_factory import build_default_workflow_engine


def build_daily_prospecting_automation() -> Automation:
    """SCHEDULED -> Prospecting Workflow (ResearchTask -> QualificationTask -> CopyTask)."""
    return Automation(
        name="Daily Prospecting",
        workflow_name="Prospecting Workflow",
        trigger=AutomationTrigger(type=AutomationTriggerType.SCHEDULED),
        schedule=AutomationSchedule(cron_expression="0 8 * * *", timezone="America/Sao_Paulo"),
    )


def build_proposal_after_qualification_automation() -> Automation:
    """EVENT -> Proposal Workflow (QualificationTask -> ProposalTask)."""
    return Automation(
        name="Proposal After Qualification",
        workflow_name="Proposal Workflow",
        trigger=AutomationTrigger(
            type=AutomationTriggerType.EVENT, event_name="prospect_qualified"
        ),
    )


def build_default_automations() -> list[Automation]:
    return [
        build_daily_prospecting_automation(),
        build_proposal_after_qualification_automation(),
    ]


def build_default_automation_engine(
    *,
    repository: AutomationRepository | None = None,
    registry: AutomationRegistry | None = None,
    workflow_engine: WorkflowEngine | None = None,
) -> AutomationEngine:
    """Composition root for this module — the *only* place in app/automation that
    imports app.workflows.services.workflow_engine_factory (which is itself what
    pulls in the ApplicationTasks/TaskExecutor/underlying engines, exactly like
    every other composition root in this codebase). AutomationEngine itself never
    sees any of that — it only receives the finished WorkflowEngine.
    """
    registry = registry or AutomationRegistry()
    if not registry.list():
        for automation in build_default_automations():
            registry.register(automation)

    return AutomationEngine(
        repository=repository or AutomationRepository(),
        registry=registry,
        workflow_engine=workflow_engine or build_default_workflow_engine(),
    )
