import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Protocol

from app.application.tasks.base.application_task import ApplicationTask, TaskType
from app.application.tasks.context.task_context import TaskContext
from app.application.tasks.executors.task_executor import TaskExecutor
from app.application.tasks.results.task_result import TaskResult
from app.workflows.exceptions.workflow_exceptions import (
    InvalidWorkflowTransitionError,
    TaskNotAvailableError,
    WorkflowNotFoundError,
)
from app.workflows.models.enums import WorkflowStatus
from app.workflows.models.workflow import Workflow
from app.workflows.models.workflow_execution import WorkflowExecution
from app.workflows.models.workflow_result import WorkflowResult
from app.workflows.models.workflow_step import WorkflowStep
from app.workflows.registry.workflow_registry import WorkflowRegistry
from app.workflows.repositories.workflow_repository import WorkflowRepository
from app.workflows.schemas.workflow_request import WorkflowRequest
from app.workflows.schemas.workflow_response import WorkflowResponse

_RESUMABLE_STATUSES = {WorkflowStatus.RUNNING, WorkflowStatus.PAUSED}


class DecisionAdapter(Protocol):
    """Structural contract for optionally choosing which Workflow to run instead
    of the one literally named in a WorkflowRequest. This is the *only* thing
    WorkflowEngine knows about Decision integration — it never imports
    app.decision or app.workflows.adapters.decision_adapter itself; a concrete
    adapter satisfying this shape (e.g. RealDecisionAdapter, which does import
    app.decision) is injected via the constructor instead. Added in Sprint 25.
    """

    def choose_workflow(self, request: WorkflowRequest) -> str: ...


class WorkflowEngine:
    """Coordinates a sequence of ApplicationTasks — nothing else. It never
    constructs a task, never imports ResearchEngine/CopyAgent/SalesIntelligence/
    OutreachEngine, and never decides *what* a task should do — only *whether the
    next one runs*, based on each step's own `continue_on_error` flag. Every task
    call goes through TaskExecutor, exactly the way any other caller in this
    codebase already reaches an ApplicationTask.

    `tasks` is a plain `{TaskType: ApplicationTask}` mapping rather than a
    TaskRegistry — the acceptance criteria for this module name exactly four things
    it may know about (ApplicationTask, TaskExecutor, TaskResult, TaskContext);
    resolving TaskType -> ApplicationTask via a registry is the composition root's
    job (workflow_engine_factory.py), not this engine's.

    `decision_adapter` is optional and defaults to None — when it is None,
    `execute()` behaves exactly as it did before Sprint 25: it runs whatever
    `WorkflowRequest.workflow_name` names, nothing more.
    """

    def __init__(
        self,
        repository: WorkflowRepository,
        registry: WorkflowRegistry,
        tasks: dict[TaskType, ApplicationTask],
        task_executor: TaskExecutor,
        decision_adapter: DecisionAdapter | None = None,
    ) -> None:
        self.repository = repository
        self.registry = registry
        self.tasks = tasks
        self.task_executor = task_executor
        self.decision_adapter = decision_adapter

    async def execute(self, request: WorkflowRequest) -> WorkflowResponse:
        workflow = self._resolve_workflow(request)
        result = await self.execute_workflow(workflow, request.context)
        return WorkflowResponse(result=result)

    def _resolve_workflow(self, request: WorkflowRequest) -> Workflow:
        """Uses `decision_adapter`, if one was given, to optionally override
        which Workflow runs. Any problem at all on this path — the adapter
        raising, or its chosen name not existing in the registry — is swallowed
        and this falls back to `request.workflow_name` exactly as before Sprint
        25. `except Exception` is deliberate here: a pluggable DecisionAdapter
        can raise anything at all, and this method must never let that change
        pre-existing behavior.
        """
        if self.decision_adapter is not None:
            try:
                chosen_name = self.decision_adapter.choose_workflow(request)
                return self.registry.get_active(chosen_name)
            except Exception:
                pass
        return self.registry.get_active(request.workflow_name)

    async def execute_step(self, step: WorkflowStep, context: TaskContext) -> TaskResult:
        task = self.tasks.get(step.task_type)
        if task is None:
            raise TaskNotAvailableError(step.task_type)

        if step.timeout is None:
            return await self.task_executor.run(task, context)

        try:
            return await asyncio.wait_for(
                self.task_executor.run(task, context), timeout=step.timeout
            )
        except asyncio.TimeoutError:
            return TaskResult(
                success=False,
                duration=step.timeout,
                errors=[f"Step '{step.name}' timed out after {step.timeout}s."],
            )

    async def execute_workflow(self, workflow: Workflow, context: TaskContext) -> WorkflowResult:
        execution = WorkflowExecution(workflow_id=workflow.id, status=WorkflowStatus.RUNNING)
        self.repository.save_execution(execution)
        ordered_steps = sorted(workflow.steps, key=lambda step: step.order)
        return await self._run_steps(execution, ordered_steps, context)

    def cancel(self, execution: WorkflowExecution) -> WorkflowExecution:
        if execution.status not in _RESUMABLE_STATUSES:
            raise InvalidWorkflowTransitionError(execution.execution_id, execution.status, "cancel")
        execution.status = WorkflowStatus.CANCELLED
        execution.finished_at = datetime.now(timezone.utc)
        return self.repository.save_execution(execution)

    async def resume(self, execution: WorkflowExecution, context: TaskContext) -> WorkflowResult:
        """Continues with the step *after* the one that paused the workflow —
        picking up where it left off without retrying the failure."""
        workflow = self._require_paused(execution)
        remaining = [
            step
            for step in sorted(workflow.steps, key=lambda step: step.order)
            if execution.current_step is None or step.order > execution.current_step
        ]
        execution.status = WorkflowStatus.RUNNING
        return await self._run_steps(execution, remaining, context)

    async def retry(self, execution: WorkflowExecution, context: TaskContext) -> WorkflowResult:
        """Re-attempts the step that paused the workflow, then continues."""
        workflow = self._require_paused(execution)
        failed_order = execution.current_step
        execution.failed_steps = [
            order for order in execution.failed_steps if order != failed_order
        ]
        remaining = [
            step
            for step in sorted(workflow.steps, key=lambda step: step.order)
            if failed_order is None or step.order >= failed_order
        ]
        execution.status = WorkflowStatus.RUNNING
        return await self._run_steps(execution, remaining, context)

    def _require_paused(self, execution: WorkflowExecution) -> Workflow:
        if execution.status != WorkflowStatus.PAUSED:
            raise InvalidWorkflowTransitionError(
                execution.execution_id, execution.status, "resume/retry"
            )
        workflow = self.registry.get_by_id(execution.workflow_id)
        if workflow is None:
            raise WorkflowNotFoundError(str(execution.workflow_id))
        return workflow

    async def _run_steps(
        self,
        execution: WorkflowExecution,
        steps: list[WorkflowStep],
        context: TaskContext,
    ) -> WorkflowResult:
        start = time.perf_counter()
        outputs: dict[str, Any] = {}

        for step in steps:
            execution.current_step = step.order
            task_result = await self.execute_step(step, context)

            if task_result.success:
                execution.completed_steps.append(step.order)
                if task_result.output is not None:
                    outputs[step.name] = task_result.output
                continue

            execution.failed_steps.append(step.order)
            execution.errors.extend(task_result.errors)
            if not step.continue_on_error:
                execution.status = WorkflowStatus.PAUSED
                self.repository.save_execution(execution)
                return self._build_result(execution, outputs, start)

            execution.warnings.append(
                f"Step '{step.name}' failed but continue_on_error=True: "
                + "; ".join(task_result.errors)
            )

        execution.status = WorkflowStatus.COMPLETED
        execution.finished_at = datetime.now(timezone.utc)
        self.repository.save_execution(execution)
        return self._build_result(execution, outputs, start)

    @staticmethod
    def _build_result(
        execution: WorkflowExecution, outputs: dict[str, Any], start: float
    ) -> WorkflowResult:
        return WorkflowResult(
            success=execution.status == WorkflowStatus.COMPLETED and not execution.failed_steps,
            execution=execution,
            outputs=outputs,
            warnings=execution.warnings,
            errors=execution.errors,
            duration=time.perf_counter() - start,
        )
