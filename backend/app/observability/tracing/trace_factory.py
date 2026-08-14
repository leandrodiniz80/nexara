from datetime import datetime, timezone

from app.observability.models.execution_step import ExecutionStatus
from app.observability.models.execution_trace import ExecutionTrace
from app.observability.tracing.trace_context import TraceContext


class TraceFactory:
    """The one place that starts a brand-new ExecutionTrace from a TraceContext —
    deterministic given its inputs (aside from the timestamp/trace_id it stamps),
    same as every other factory in this codebase that composes a fresh entity."""

    @staticmethod
    def create(context: TraceContext, execution_type: str) -> ExecutionTrace:
        return ExecutionTrace(
            correlation_id=context.correlation_id,
            request_id=context.request_id,
            mission_id=context.mission_id,
            job_id=context.job_id,
            task_id=context.task_id,
            execution_type=execution_type,
            started_at=datetime.now(timezone.utc),
            status=ExecutionStatus.RUNNING,
            metadata=dict(context.metadata),
        )
