from app.events.exceptions.base import EventError


class HandlerNotSubscribedError(EventError):
    """Raised by EventBus.unsubscribe() when asked to remove a handler that was never
    subscribed to that event — surfaced explicitly rather than silently no-op'ing,
    since a mismatched unsubscribe usually means a bug in whoever called it."""

    def __init__(self, event_name: str, handler: object) -> None:
        self.event_name = event_name
        self.handler = handler
        super().__init__(f"Handler {handler!r} is not subscribed to '{event_name}'.")
