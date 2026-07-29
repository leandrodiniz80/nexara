import uuid

from app.events.bus.event_bus import EventBus
from app.events.handlers.event_handler import EventHandler
from app.events.registry.event_registry import EventRegistry
from app.events.schemas.domain_event import DomainEvent
from app.events.schemas.mission_events import MissionCreated, MissionStarted


class _Handler(EventHandler):
    """event_name is set per-instance here purely for test convenience — real handlers
    fix it as a class attribute (see EventHandler's own docstring)."""

    def __init__(self, event_name: str) -> None:
        self.event_name = event_name
        self.received: list[DomainEvent] = []

    async def handle(self, event: DomainEvent) -> None:
        self.received.append(event)


def test_register_collects_handlers_without_touching_the_bus():
    registry = EventRegistry()
    handler = _Handler("mission.created")

    registry.register(handler)

    assert registry.handlers == [handler]


async def test_attach_subscribes_every_registered_handler():
    registry = EventRegistry()
    created_handler = _Handler("mission.created")
    started_handler = _Handler("mission.started")
    registry.register_many([created_handler, started_handler])

    bus = EventBus()
    registry.attach(bus)

    created = MissionCreated(aggregate_id=uuid.uuid4())
    started = MissionStarted(aggregate_id=uuid.uuid4())
    await bus.publish(created)
    await bus.publish(started)

    assert created_handler.received == [created]
    assert started_handler.received == [started]
