from typing import Any, ClassVar

from app.application.tasks.base.application_task import ApplicationTask, TaskType
from app.application.tasks.context.task_context import TaskContext
from app.application.tasks.exceptions.task_exceptions import TaskValidationError
from app.sales_intelligence.engine.sales_intelligence_engine import SalesIntelligenceEngine


class QualificationTask(ApplicationTask):
    """QualificationTask -> SalesIntelligenceEngine -> TaskResult.

    SalesIntelligenceEngine.analyze_company() is synchronous (it's pure computation,
    no I/O) — awaited nowhere, called directly inside this async execute(), same as
    any other sync call inside an async function.
    """

    task_type: ClassVar[TaskType] = TaskType.QUALIFICATION
    name: ClassVar[str] = "qualification_task"

    def __init__(self, sales_intelligence_engine: SalesIntelligenceEngine) -> None:
        self.sales_intelligence_engine = sales_intelligence_engine

    def validate(self, context: TaskContext) -> None:
        if "profile" not in context.variables:
            raise TaskValidationError(
                "QualificationTask requires TaskContext.variables['profile'] "
                "(a CommercialProfile)."
            )

    async def execute(self, context: TaskContext) -> dict[str, Any]:
        profile = context.variables["profile"]
        reference = context.company_id or context.prospect_id
        result = self.sales_intelligence_engine.analyze_company(profile, reference=reference)
        return result.model_dump(mode="json")

    async def rollback(self, context: TaskContext) -> None:
        """analyze_company() only writes to SalesIntelligenceRepository when a
        `reference` is given, and that repository has no delete() to compensate
        with (frozen module) — best-effort no-op."""
