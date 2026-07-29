from typing import Literal

from app.events.schemas.domain_event import DomainEvent


class WorkflowStarted(DomainEvent):
    """No persisted Workflow entity exists yet — aggregate_id is a fresh id identifying
    one run of whatever multi-step process this is (e.g. the outreach sequence for a
    single prospect). Conventional payload: workflow_name, triggered_by."""

    event_name: Literal["workflow.started"] = "workflow.started"
    aggregate_type: Literal["workflow"] = "workflow"


class WorkflowFinished(DomainEvent):
    """Conventional payload: steps_completed, duration_seconds."""

    event_name: Literal["workflow.finished"] = "workflow.finished"
    aggregate_type: Literal["workflow"] = "workflow"


class WorkflowFailed(DomainEvent):
    """Conventional payload: failed_step, reason."""

    event_name: Literal["workflow.failed"] = "workflow.failed"
    aggregate_type: Literal["workflow"] = "workflow"
