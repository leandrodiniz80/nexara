import uuid

from app.events.bus.event_bus import EventBus
from app.events.handlers.event_handler import EventHandler
from app.events.publishers.event_publisher import EventPublisher
from app.events.schemas.domain_event import DomainEvent
from app.events.schemas.mission_events import MissionCreated
from app.events.subscribers.event_subscriber import EventSubscriber


class _Handler(EventHandler):
    def __init__(self, event_name: str) -> None:
        self.event_name = event_name
        self.received: list[DomainEvent] = []

    async def handle(self, event: DomainEvent) -> None:
        self.received.append(event)


async def test_publish_mints_a_fresh_correlation_and_trace_id_for_a_root_event():
    bus = EventBus()
    publisher = EventPublisher(bus)
    event = MissionCreated(aggregate_id=uuid.uuid4())

    envelope = await publisher.publish(event)

    assert envelope.event is event
    assert envelope.correlation_id is not None
    assert envelope.trace_id is not None
    assert envelope.causation_id is None


async def test_publish_reuses_correlation_carried_in_event_metadata():
    bus = EventBus()
    publisher = EventPublisher(bus)
    correlation_id = uuid.uuid4()
    trace_id = uuid.uuid4()
    event = MissionCreated(
        aggregate_id=uuid.uuid4(), metadata={"correlation_id": correlation_id, "trace_id": trace_id}
    )

    envelope = await publisher.publish(event)

    assert envelope.correlation_id == correlation_id
    assert envelope.trace_id == trace_id


async def test_publish_many_shares_one_correlation_id_across_the_batch():
    bus = EventBus()
    publisher = EventPublisher(bus)
    events = [MissionCreated(aggregate_id=uuid.uuid4()) for _ in range(3)]

    envelopes = await publisher.publish_many(events)

    correlation_ids = {envelope.correlation_id for envelope in envelopes}
    assert len(correlation_ids) == 1


async def test_subscriber_subscribe_and_unsubscribe_all():
    bus = EventBus()
    subscriber = EventSubscriber(bus)
    handler = _Handler("mission.created")
    subscriber.subscribe(handler)

    await bus.publish(MissionCreated(aggregate_id=uuid.uuid4()))
    assert len(handler.received) == 1

    subscriber.unsubscribe_all()
    await bus.publish(MissionCreated(aggregate_id=uuid.uuid4()))
    assert len(handler.received) == 1  # no new deliveries after unsubscribing


async def test_unsubscribe_all_is_safe_to_call_twice():
    bus = EventBus()
    subscriber = EventSubscriber(bus)
    subscriber.subscribe(_Handler("mission.created"))

    subscriber.unsubscribe_all()
    subscriber.unsubscribe_all()  # must not raise HandlerNotSubscribedError the second time
