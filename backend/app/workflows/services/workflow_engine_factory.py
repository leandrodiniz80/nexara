from app.application.tasks.base.application_task import ApplicationTask, TaskType
from app.application.tasks.executors.task_executor import TaskExecutor
from app.application.tasks.task_factory import TaskFactory
from app.workflows.builders.default_workflows import build_default_workflows
from app.workflows.engine.workflow_engine import DecisionAdapter, WorkflowEngine
from app.workflows.registry.workflow_registry import WorkflowRegistry
from app.workflows.repositories.workflow_repository import WorkflowRepository


def build_default_workflow_engine(
    *,
    repository: WorkflowRepository | None = None,
    registry: WorkflowRegistry | None = None,
    tasks: dict[TaskType, ApplicationTask] | None = None,
    task_executor: TaskExecutor | None = None,
    decision_adapter: DecisionAdapter | None = None,
) -> WorkflowEngine:
    """Composition root for this module — the *only* place in app/workflows that
    imports app.application.tasks.task_factory (which is itself what pulls in
    AIOrchestrator/OutreachEngine/SalesIntelligenceEngine/LeadDiscoveryPipeline,
    exactly like every other composition root in this codebase already does).
    WorkflowEngine itself never sees any of that — it only receives the finished
    `{TaskType: ApplicationTask}` mapping.

    `decision_adapter` defaults to None, so every existing caller of this
    function keeps getting the exact same WorkflowEngine behavior as before
    Sprint 25. A caller that wants Decision integration builds a
    RealDecisionAdapter (app.workflows.adapters.decision_adapter) itself and
    passes it in — this factory does not construct one automatically, since
    doing so would silently change behavior for every existing caller.
    """
    registry = registry or WorkflowRegistry()
    if not registry.list_workflows():
        for workflow in build_default_workflows():
            registry.register(workflow)

    if tasks is None:
        tasks = {task.task_type: task for task in TaskFactory().build_all()}

    return WorkflowEngine(
        repository=repository or WorkflowRepository(),
        registry=registry,
        tasks=tasks,
        task_executor=task_executor or TaskExecutor(),
        decision_adapter=decision_adapter,
    )
