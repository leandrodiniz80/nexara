from typing import Any, ClassVar, Protocol

from app.application.tasks.base.application_task import ApplicationTask, TaskType
from app.application.tasks.context.task_context import TaskContext
from app.application.tasks.exceptions.task_exceptions import (
    TaskExecutionError,
    TaskValidationError,
)
from app.research.pipeline.pipeline_context import PipelineContext
from app.research.pipeline.pipeline_report import PipelineReport
from app.research.pipeline.strategy_kind import StrategyKind


class _SupportsPipelineExecute(Protocol):
    async def execute(self, context: Any) -> Any: ...


class ResearchTask(ApplicationTask):
    """ResearchTask -> LeadDiscoveryPipeline -> TaskResult.

    Depends structurally on "anything with an async execute(context) -> report"
    (checked via `_SupportsPipelineExecute`, the same Protocol idiom
    PipelineJobExecutor already uses in app/jobs) rather than importing
    LeadDiscoveryPipeline by name — this task doesn't need to know which pipeline it
    is, only that it behaves like one.
    """

    task_type: ClassVar[TaskType] = TaskType.RESEARCH
    name: ClassVar[str] = "research_task"

    def __init__(self, pipeline: _SupportsPipelineExecute) -> None:
        self.pipeline = pipeline

    def validate(self, context: TaskContext) -> None:
        if context.mission_id is None:
            raise TaskValidationError("ResearchTask requires TaskContext.mission_id.")
        if "strategy" not in context.variables:
            raise TaskValidationError("ResearchTask requires TaskContext.variables['strategy'].")
        try:
            StrategyKind(context.variables["strategy"])
        except ValueError as exc:
            raise TaskValidationError(
                f"Unknown strategy '{context.variables['strategy']}'."
            ) from exc

    async def execute(self, context: TaskContext) -> dict[str, Any]:
        pipeline_context = PipelineContext(
            mission_id=context.mission_id,
            requested_by=context.requested_by,
            strategy=StrategyKind(context.variables["strategy"]),
            query=context.variables.get("query", {}),
            filters=context.variables.get("filters", {}),
        )
        report: PipelineReport = await self.pipeline.execute(pipeline_context)
        if report.errors:
            raise TaskExecutionError(f"LeadDiscoveryPipeline failed: {'; '.join(report.errors)}")
        return report.model_dump(mode="json")

    async def rollback(self, context: TaskContext) -> None:
        """LeadDiscoveryPipeline already rolls its own completed steps back on
        failure (see LeadDiscoveryPipeline.execute()) — there is nothing left here
        for the Task layer to compensate."""
