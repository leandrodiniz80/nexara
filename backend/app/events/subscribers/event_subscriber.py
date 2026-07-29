from app.events.bus.event_bus import EventBus
from app.events.handlers.event_handler import EventHandler


class EventSubscriber:
    """What a module holds to register its own EventHandlers against a bus — the
    subscribe-side counterpart to EventPublisher. Tracks what it subscribed so it can
    cleanly unsubscribe_all() later (module teardown, test isolation), rather than
    every caller having to remember which (event_name, handler) pairs it registered.
    """

    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self._subscribed: list[tuple[str, EventHandler]] = []

    def subscribe(self, handler: EventHandler) -> None:
        self.bus.subscribe(handler.event_name, handler)
        self._subscribed.append((handler.event_name, handler))

    def subscribe_many(self, handlers: list[EventHandler]) -> None:
        for handler in handlers:
            self.subscribe(handler)

    def unsubscribe_all(self) -> None:
        for event_name, handler in self._subscribed:
            self.bus.unsubscribe(event_name, handler)
        self._subscribed.clear()
