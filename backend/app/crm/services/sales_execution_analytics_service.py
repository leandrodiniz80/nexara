from datetime import datetime, timezone

from app.crm.services.sales_enrollment import SalesEnrollment
from app.crm.services.sales_execution_analytics import SalesExecutionAnalytics
from app.crm.services.sales_execution_metrics import SalesExecutionMetrics
from app.crm.services.sales_timeline import SalesTimeline

_STARTED_EVENT = "started"
_FINISHED_EVENT = "finished"
_PAUSED_EVENT = "paused"
_RESUMED_EVENT = "resumed"
_ROLLED_BACK_EVENT = "step_rolled_back"


class SalesExecutionAnalyticsService:
    """Calculates SalesExecutionMetrics from an enrollment's current
    SalesCadenceExecution state and its SalesTimeline history — nothing
    more. A pure, deterministic calculation: no persistence, no CRMEngine,
    no Runtime, no Workflow, no Automation, no AI, no Rule, no Decision, no
    Adapter. `finished`/`pause_count`/`resume_count`/`rollback_count` are
    read exclusively from the timeline's own events, never from the
    execution's own (mutable, currently-can-be-rolled-back) status — so a
    cadence that was finished and later rolled back still shows up as
    having been finished at least once in its history.
    """

    def analyze(
        self,
        enrollment: SalesEnrollment,
        timeline: SalesTimeline,
        *,
        now: datetime | None = None,
    ) -> SalesExecutionAnalytics:
        now = now or datetime.now(timezone.utc)
        execution = enrollment.execution

        started_events = [e for e in timeline.events if e.event_type == _STARTED_EVENT]
        finished_events = [e for e in timeline.events if e.event_type == _FINISHED_EVENT]
        pause_count = sum(1 for e in timeline.events if e.event_type == _PAUSED_EVENT)
        resume_count = sum(1 for e in timeline.events if e.event_type == _RESUMED_EVENT)
        rollback_count = sum(1 for e in timeline.events if e.event_type == _ROLLED_BACK_EVENT)
        finished = bool(finished_events)

        started_at = started_events[0].occurred_at if started_events else None
        finished_at = finished_events[-1].occurred_at if finished else None

        if started_at is None:
            total_duration = None
        elif finished_at is not None:
            total_duration = finished_at - started_at
        else:
            total_duration = now - started_at

        metrics = SalesExecutionMetrics(
            total_steps=enrollment.cadence.total_steps,
            completed_steps=len(execution.completed_steps),
            remaining_steps=len(execution.remaining_steps),
            completion_rate=execution.progress,
            total_events=len(timeline.events),
            pause_count=pause_count,
            resume_count=resume_count,
            rollback_count=rollback_count,
            finished=finished,
            started_at=started_at,
            finished_at=finished_at,
            total_duration=total_duration,
        )
        return SalesExecutionAnalytics(
            enrollment=enrollment,
            timeline=timeline,
            metrics=metrics,
            generated_at=now,
        )
