from datetime import datetime, timedelta, timezone

from app.crm.models.crm_opportunity import CRMOpportunity
from app.crm.services.sales_cadence import SalesCadence
from app.crm.services.sales_cadence_execution import (
    SalesCadenceExecution,
    SalesCadenceExecutionStatus,
)


class SalesCadenceExecutionService:
    """Controls which step of an already-built SalesCadence one opportunity
    currently occupies — nothing more. It never builds a cadence
    (SalesCadenceService remains the only place that defines the sequence
    of steps), never persists anything, and calls no other module: not
    CRMEngine, not Runtime, not Workflow, not Automation, not Scheduler,
    not Decision, not Business Rules, not Observability. It is a pure
    controller over a SalesCadenceExecution's own in-memory state.
    """

    def start(
        self,
        cadence: SalesCadence,
        opportunity: CRMOpportunity,
        *,
        now: datetime | None = None,
    ) -> SalesCadenceExecution:
        now = now or datetime.now(timezone.utc)
        warnings = list(cadence.warnings)

        if not cadence.steps:
            warnings.append("Cadence has no steps to execute.")
            return SalesCadenceExecution(
                status=SalesCadenceExecutionStatus.FINISHED,
                started_at=now,
                last_activity=now,
                finished_at=now,
                progress=100.0,
                warnings=warnings,
            )

        first_step = cadence.steps[0]
        execution = SalesCadenceExecution(
            current_step=first_step,
            remaining_steps=list(cadence.steps[1:]),
            status=SalesCadenceExecutionStatus.IN_PROGRESS,
            started_at=now,
            last_activity=now,
            next_due_date=now.date() + timedelta(days=first_step.recommended_delay),
            warnings=warnings,
        )
        execution.progress = self._progress(execution)
        return execution

    def advance(
        self, execution: SalesCadenceExecution, *, now: datetime | None = None
    ) -> SalesCadenceExecution:
        now = now or datetime.now(timezone.utc)

        if execution.status == SalesCadenceExecutionStatus.FINISHED:
            execution.warnings.append("Cadence is already finished; advance() had no effect.")
            return execution

        if not execution.remaining_steps:
            return self.finish(execution, now=now)

        if execution.current_step is not None:
            execution.completed_steps = execution.completed_steps + [execution.current_step]

        next_step = execution.remaining_steps[0]
        execution.remaining_steps = execution.remaining_steps[1:]
        execution.current_step = next_step
        execution.status = SalesCadenceExecutionStatus.IN_PROGRESS
        execution.last_activity = now
        execution.next_due_date = now.date() + timedelta(days=next_step.recommended_delay)
        execution.progress = self._progress(execution)
        return execution

    def rollback(
        self, execution: SalesCadenceExecution, *, now: datetime | None = None
    ) -> SalesCadenceExecution:
        now = now or datetime.now(timezone.utc)

        if not execution.completed_steps:
            execution.warnings.append("Cannot rollback before the first step.")
            return execution

        if execution.current_step is not None:
            execution.remaining_steps = [execution.current_step] + execution.remaining_steps

        previous_step = execution.completed_steps[-1]
        execution.completed_steps = execution.completed_steps[:-1]
        execution.current_step = previous_step
        execution.status = SalesCadenceExecutionStatus.IN_PROGRESS
        execution.finished_at = None
        execution.last_activity = now
        execution.next_due_date = now.date() + timedelta(days=previous_step.recommended_delay)
        execution.progress = self._progress(execution)
        return execution

    def pause(
        self, execution: SalesCadenceExecution, *, now: datetime | None = None
    ) -> SalesCadenceExecution:
        now = now or datetime.now(timezone.utc)

        if execution.status == SalesCadenceExecutionStatus.FINISHED:
            execution.warnings.append("Cannot pause a finished cadence.")
            return execution

        execution.status = SalesCadenceExecutionStatus.PAUSED
        execution.last_activity = now
        return execution

    def resume(
        self, execution: SalesCadenceExecution, *, now: datetime | None = None
    ) -> SalesCadenceExecution:
        now = now or datetime.now(timezone.utc)

        if execution.status != SalesCadenceExecutionStatus.PAUSED:
            execution.warnings.append("Cannot resume a cadence that is not paused.")
            return execution

        execution.status = SalesCadenceExecutionStatus.IN_PROGRESS
        execution.last_activity = now
        return execution

    def finish(
        self, execution: SalesCadenceExecution, *, now: datetime | None = None
    ) -> SalesCadenceExecution:
        now = now or datetime.now(timezone.utc)

        if execution.current_step is not None:
            execution.completed_steps = execution.completed_steps + [execution.current_step]
            execution.current_step = None

        execution.remaining_steps = []
        execution.status = SalesCadenceExecutionStatus.FINISHED
        execution.finished_at = now
        execution.last_activity = now
        execution.next_due_date = None
        execution.progress = self._progress(execution)
        return execution

    @staticmethod
    def _progress(execution: SalesCadenceExecution) -> float:
        total = (
            len(execution.completed_steps)
            + (1 if execution.current_step is not None else 0)
            + len(execution.remaining_steps)
        )
        if total == 0:
            return 100.0
        return round(len(execution.completed_steps) / total * 100, 2)
