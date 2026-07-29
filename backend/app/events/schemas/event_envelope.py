import uuid

from pydantic import BaseModel, ConfigDict

from app.events.schemas.domain_event import DomainEvent


class EventEnvelope(BaseModel):
    """The "receipt" of one EventPublisher.publish() call: the event plus everything
    needed to trace it through a chain of causally-related events (correlation_id ties
    an entire saga together; causation_id points at the one event that triggered this
    one; trace_id is the cross-cutting id a future observability layer would use).

    EventBus itself only ever deals with bare DomainEvent for subscribe/dispatch
    routing — envelopes are EventPublisher's concern, not the bus's.
    """

    model_config = ConfigDict(frozen=True)

    correlation_id: uuid.UUID
    causation_id: uuid.UUID | None = None
    trace_id: uuid.UUID
    tenant_id: str | None = None
    user_id: uuid.UUID | None = None
    event: DomainEvent
