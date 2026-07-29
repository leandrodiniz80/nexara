from typing import Literal

from app.events.schemas.domain_event import DomainEvent


class EmailGenerated(DomainEvent):
    """aggregate_id is the prospect this email is for — no persisted "sent email"
    table exists yet, so these events are the closest thing to a record of the email
    funnel until MissionMetrics' emails_* counters get a real source to increment from.
    Conventional payload: template_name, subject.
    """

    event_name: Literal["email.generated"] = "email.generated"
    aggregate_type: Literal["prospect"] = "prospect"


class EmailApproved(DomainEvent):
    """Conventional payload: approved_by."""

    event_name: Literal["email.approved"] = "email.approved"
    aggregate_type: Literal["prospect"] = "prospect"


class EmailSent(DomainEvent):
    """Conventional payload: sent_at, provider."""

    event_name: Literal["email.sent"] = "email.sent"
    aggregate_type: Literal["prospect"] = "prospect"


class EmailOpened(DomainEvent):
    """Conventional payload: opened_at."""

    event_name: Literal["email.opened"] = "email.opened"
    aggregate_type: Literal["prospect"] = "prospect"


class EmailReplied(DomainEvent):
    """Conventional payload: replied_at, sentiment."""

    event_name: Literal["email.replied"] = "email.replied"
    aggregate_type: Literal["prospect"] = "prospect"
