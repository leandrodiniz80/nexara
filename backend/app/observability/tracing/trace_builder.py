from datetime import datetime, timezone

from app.observability.exceptions.observability_exceptions import InvalidTraceTransitionError
from app.observability.models.execution_step import ExecutionStatus, ExecutionStep
from app.observability.models.execution_trace import ExecutionTrace


class TraceBuilder:
    """Deterministic construction/mutation of ExecutionTrace and ExecutionStep —
    every method here is a pure function of its inputs (plus, for `finish`/
    `append_step`, the trace passed in): no I/O, no repository access, no decision
    beyond guarding the RUNNING -> {SUCCESS, FAILED} state machine. That guarding
    lives here rather than in ObservabilityEngine so the rule (a finished trace
    accepts no more steps) can't be bypassed by whichever caller builds a step.
    """

    @staticmethod
    def build_step(
        *,
        step_name: str,
        component: str,
        started_at: datetime,
        finished_at: datetime,
        status: ExecutionStatus,
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
    ) -> ExecutionStep:
        return ExecutionStep(
            step_name=step_name,
            component=component,
            started_at=started_at,
            finished_at=finished_at,
            duration=(finished_at - started_at).total_seconds(),
            status=status,
            warnings=warnings or [],
            errors=errors or [],
        )

    @staticmethod
    def append_step(trace: ExecutionTrace, step: ExecutionStep) -> ExecutionTrace:
        if trace.status != ExecutionStatus.RUNNING:
            raise InvalidTraceTransitionError(trace.trace_id, trace.status, "register_step")
        trace.steps.append(step)
        return trace

    @staticmethod
    def finish(
        trace: ExecutionTrace, *, status: ExecutionStatus, finished_at: datetime | None = None
    ) -> ExecutionTrace:
        if trace.status != ExecutionStatus.RUNNING:
            raise InvalidTraceTransitionError(trace.trace_id, trace.status, "finish_trace")
        if status == ExecutionStatus.RUNNING:
            raise InvalidTraceTransitionError(trace.trace_id, trace.status, "finish_trace")
        finished_at = finished_at or datetime.now(timezone.utc)
        trace.finished_at = finished_at
        trace.duration = (finished_at - trace.started_at).total_seconds()
        trace.status = status
        return trace
