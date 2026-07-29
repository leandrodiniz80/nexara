import uuid

from app.events.bus.event_bus import EventBus
from app.events.schemas.domain_event import DomainEvent
from app.events.schemas.event_envelope import EventEnvelope


class EventPublisher:
    """What a domain service holds to emit events — never the raw EventBus directly.

    Wraps every publish() call in an EventEnvelope, resolving correlation_id/trace_id/
    causation_id from (in order): the explicit keyword argument, whatever `event`'s own
    metadata already carries, or — only for correlation_id/trace_id — a freshly minted
    id if this is the first event of a chain.

    Before dispatching, the resolved ids are written into `event.metadata` in place.
    DomainEvent is frozen, but `frozen` only blocks *reassigning* a field (`event.metadata
    = {...}` would raise) — mutating the dict object already stored in that field is not
    a field reassignment, so this is allowed and is the mechanism that makes correlation
    survive a chain: a handler's `event.derive_metadata()` reads back exactly what got
    stamped here, so the *next* event it constructs inherits the same correlation_id/
    trace_id, with causation_id updated to point at the event that caused it.
    """

    def __init__(self, bus: EventBus) -> None:
        self.bus = bus

    async def publish(
        self,
        event: DomainEvent,
        *,
        correlation_id: uuid.UUID | None = None,
        causation_id: uuid.UUID | None = None,
        trace_id: uuid.UUID | None = None,
        tenant_id: str | None = None,
        user_id: uuid.UUID | None = None,
    ) -> EventEnvelope:
        resolved_correlation_id = correlation_id or event.metadata.get("correlation_id") or uuid.uuid4()
        resolved_causation_id = causation_id or event.metadata.get("causation_id")
        resolved_trace_id = trace_id or event.metadata.get("trace_id") or uuid.uuid4()
        resolved_tenant_id = tenant_id or event.metadata.get("tenant_id")
        resolved_user_id = user_id or event.metadata.get("user_id")

        event.metadata["correlation_id"] = resolved_correlation_id
        event.metadata["trace_id"] = resolved_trace_id
        if resolved_causation_id is not None:
            event.metadata["causation_id"] = resolved_causation_id
        if resolved_tenant_id is not None:
            event.metadata["tenant_id"] = resolved_tenant_id
        if resolved_user_id is not None:
            event.metadata["user_id"] = resolved_user_id

        envelope = EventEnvelope(
            correlation_id=resolved_correlation_id,
            causation_id=resolved_causation_id,
            trace_id=resolved_trace_id,
            tenant_id=resolved_tenant_id,
            user_id=resolved_user_id,
            event=event,
        )
        await self.bus.publish(event)
        return envelope

    async def publish_many(
        self,
        events: list[DomainEvent],
        *,
        correlation_id: uuid.UUID | None = None,
        causation_id: uuid.UUID | None = None,
        trace_id: uuid.UUID | None = None,
        tenant_id: str | None = None,
        user_id: uuid.UUID | None = None,
    ) -> list[EventEnvelope]:
        """Publishes every event under the same correlation_id/trace_id — useful when
        one action produces several sibling events at once, as opposed to a causal
        chain where each event triggers the next (see DomainEvent.derive_metadata()).

        Without an explicit correlation_id/trace_id, one pair is minted once for the
        whole batch (not once per event) so "the same" promise above actually holds.
        """
        correlation_id = correlation_id or uuid.uuid4()
        trace_id = trace_id or uuid.uuid4()
        return [
            await self.publish(
                event,
                correlation_id=correlation_id,
                causation_id=causation_id,
                trace_id=trace_id,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            for event in events
        ]
