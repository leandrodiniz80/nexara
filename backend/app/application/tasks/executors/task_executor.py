import time

from app.application.tasks.base.application_task import ApplicationTask
from app.application.tasks.context.task_context import TaskContext
from app.application.tasks.results.task_result import TaskResult


class TaskExecutor:
    """Runs any ApplicationTask to completion: validate -> execute, timed and always
    wrapped into a TaskResult — even on failure, so a broken task can never raise
    past this boundary. On failure, best-effort calls the task's own rollback()
    before reporting. Same shape as AgentBase.execute() (app/ai) and
    PipelineJobExecutor.execute() (app/jobs) for the same reason: whatever actually
    does the work varies, but how its outcome is measured and reported should not.
    """

    async def run(self, task: ApplicationTask, context: TaskContext) -> TaskResult:
        start = time.perf_counter()
        logs: list[str] = []
        try:
            task.validate(context)
            logs.append(f"{task.name}: validated")
            output = await task.execute(context)
            logs.append(f"{task.name}: executed")
            return TaskResult(
                success=True,
                output=output,
                duration=time.perf_counter() - start,
                logs=logs,
            )
        except Exception as exc:  # a task must never raise past the executor
            logs.append(f"{task.name}: failed - {exc}")
            try:
                await task.rollback(context)
                logs.append(f"{task.name}: rolled back")
            except Exception as rollback_exc:
                logs.append(f"{task.name}: rollback also failed - {rollback_exc}")
            return TaskResult(
                success=False,
                errors=[str(exc)],
                duration=time.perf_counter() - start,
                logs=logs,
            )
