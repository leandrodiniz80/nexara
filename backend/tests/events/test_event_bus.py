import uuid
from typing import ClassVar

import pytest

from app.events.bus.event_bus import EventBus
from app.events.exceptions.bus_exceptions import HandlerNotSubscribedError
from app.events.handlers.event_handler import EventHandler
from app.events.schemas.domain_event import DomainEvent
from app.events.schemas.mission_events import MissionCreated, MissionStarted


class _RecordingHandler(EventHandler):
    event_name: ClassVar[str] = "mission.created"

    def __init__(self) -> None:
        self.received: list[DomainEvent] = []

    async def handle(self, event: DomainEvent) -> None:
        self.received.append(event)


class _BrokenHandler(EventHandler):
    event_name: ClassVar[str] = "mission.created"

    async def handle(self, event: DomainEvent) -> None:
        raise RuntimeError("boom")


async def test_publish_calls_every_subscriber_of_that_event_name():
    bus = EventBus()
    handler = _RecordingHandler()
    bus.subscribe("mission.created", handler)
    event = MissionCreated(aggregate_id=uuid.uuid4())

    await bus.publish(event)

    assert handler.received == [event]


async def test_publish_ignores_handlers_of_other_event_names():
    bus = EventBus()
    handler = _RecordingHandler()
    bus.subscribe("mission.started", handler)

    await bus.publish(MissionCreated(aggregate_id=uuid.uuid4()))

    assert handler.received == []


async def test_publish_many_dispatches_every_event_in_order():
    bus = EventBus()
    handler = _RecordingHandler()
    bus.subscribe("mission.created", handler)
    events = [MissionCreated(aggregate_id=uuid.uuid4()) for _ in range(3)]

    await bus.publish_many(events)

    assert handler.received == events


async def test_a_failing_handler_does_not_stop_the_others_or_raise():
    bus = EventBus()
    broken = _BrokenHandler()
    recording = _RecordingHandler()
    bus.subscribe("mission.created", broken)
    bus.subscribe("mission.created", recording)
    event = MissionCreated(aggregate_id=uuid.uuid4())

    logs = await bus.publish(event)

    assert recording.received == [event]
    assert len(logs) == 2
    broken_log = next(log for log in logs if log.handler == "_BrokenHandler")
    assert broken_log.success is False
    assert broken_log.error == "boom"
    recording_log = next(log for log in logs if log.handler == "_RecordingHandler")
    assert recording_log.success is True
    assert recording_log.error is None


async def test_execution_logs_accumulate_across_publishes():
    bus = EventBus()
    bus.subscribe("mission.created", _RecordingHandler())

    await bus.publish(MissionCreated(aggregate_id=uuid.uuid4()))
    await bus.publish(MissionCreated(aggregate_id=uuid.uuid4()))

    assert len(bus.list_execution_logs()) == 2


def test_unsubscribe_removes_the_handler():
    bus = EventBus()
    handler = _RecordingHandler()
    bus.subscribe("mission.created", handler)

    bus.unsubscribe("mission.created", handler)

    assert bus.subscriber_count("mission.created") == 0


def test_unsubscribe_raises_when_handler_was_never_subscribed():
    bus = EventBus()
    handler = _RecordingHandler()

    with pytest.raises(HandlerNotSubscribedError):
        bus.unsubscribe("mission.created", handler)


async def test_dispatch_with_no_subscribers_returns_empty_logs():
    bus = EventBus()

    logs = await bus.dispatch(MissionStarted(aggregate_id=uuid.uuid4()))

    assert logs == []
