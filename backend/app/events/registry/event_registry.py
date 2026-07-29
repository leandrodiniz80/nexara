from app.events.bus.event_bus import EventBus
from app.events.handlers.event_handler import EventHandler


class EventRegistry:
    """Collects every EventHandler the application knows about and wires them all onto
    an EventBus in one call — "register automatically" instead of the composition
    root hand-writing one bus.subscribe() per handler. A module contributes its
    handlers here once (e.g. at startup); EventRegistry.attach(bus) does the rest.
    """

    def __init__(self) -> None:
        self._handlers: list[EventHandler] = []

    def register(self, handler: EventHandler) -> EventHandler:
        self._handlers.append(handler)
        return handler

    def register_many(self, handlers: list[EventHandler]) -> list[EventHandler]:
        for handler in handlers:
            self.register(handler)
        return handlers

    def attach(self, bus: EventBus) -> None:
        """Subscribes every registered handler onto `bus`, keyed by its event_name."""
        for handler in self._handlers:
            bus.subscribe(handler.event_name, handler)

    @property
    def handlers(self) -> list[EventHandler]:
        return list(self._handlers)
