from datetime import datetime, timezone
from typing import Any

from app.crm.services.sales_cadence_step import SalesCadenceStep
from app.crm.services.sales_enrollment import SalesEnrollment
from app.crm.services.sales_timeline import SalesTimeline
from app.crm.services.sales_timeline_event import SalesTimelineEvent


class SalesTimelineService:
    """Records what happened during an enrollment's commercial journey —
    nothing more. Every operation returns a brand new SalesTimeline with one
    more SalesTimelineEvent appended to the end; the previous SalesTimeline,
    and every event it already held, are left exactly as they were.

    It knows nothing about CRMEngine, Runtime, Workflow, Automation,
    Scheduler, AI, Rules or Decisions, and it calls none of them: it only
    ever reads the SalesEnrollment/SalesCadenceStep values its caller
    already has and appends a record of what they mean.
    """

    def create(
        self,
        enrollment: SalesEnrollment,
        *,
        now: datetime | None = None,
    ) -> SalesTimeline:
        now = now or datetime.now(timezone.utc)
        return SalesTimeline(enrollment=enrollment, events=[], created_at=now, last_updated=now)

    def record_started(
        self,
        timeline: SalesTimeline,
        *,
        step: SalesCadenceStep | None = None,
        now: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SalesTimeline:
        return self._append(
            timeline,
            event_type="started",
            description="Cadência iniciada.",
            step=step,
            now=now,
            metadata=metadata,
        )

    def record_step_completed(
        self,
        timeline: SalesTimeline,
        step: SalesCadenceStep,
        *,
        now: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SalesTimeline:
        return self._append(
            timeline,
            event_type="step_completed",
            description=f"Etapa concluída: {step.action}.",
            step=step,
            now=now,
            metadata=metadata,
        )

    def record_step_rolled_back(
        self,
        timeline: SalesTimeline,
        step: SalesCadenceStep,
        *,
        now: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SalesTimeline:
        return self._append(
            timeline,
            event_type="step_rolled_back",
            description=f"Retorno para a etapa: {step.action}.",
            step=step,
            now=now,
            metadata=metadata,
        )

    def record_paused(
        self,
        timeline: SalesTimeline,
        *,
        now: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SalesTimeline:
        return self._append(
            timeline,
            event_type="paused",
            description="Cadência pausada.",
            now=now,
            metadata=metadata,
        )

    def record_resumed(
        self,
        timeline: SalesTimeline,
        *,
        now: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SalesTimeline:
        return self._append(
            timeline,
            event_type="resumed",
            description="Cadência retomada.",
            now=now,
            metadata=metadata,
        )

    def record_finished(
        self,
        timeline: SalesTimeline,
        *,
        now: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SalesTimeline:
        return self._append(
            timeline,
            event_type="finished",
            description="Cadência finalizada.",
            now=now,
            metadata=metadata,
        )

    @staticmethod
    def _append(
        timeline: SalesTimeline,
        *,
        event_type: str,
        description: str,
        step: SalesCadenceStep | None = None,
        now: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SalesTimeline:
        now = now or datetime.now(timezone.utc)
        event = SalesTimelineEvent(
            occurred_at=now,
            event_type=event_type,
            description=description,
            step_number=step.step_number if step is not None else None,
            step_name=step.action if step is not None else None,
            metadata=dict(metadata or {}),
        )
        return SalesTimeline(
            enrollment=timeline.enrollment,
            events=timeline.events + [event],
            created_at=timeline.created_at,
            last_updated=now,
        )
