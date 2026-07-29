import time
from collections import defaultdict

from app.events.exceptions.bus_exceptions import HandlerNotSubscribedError
from app.events.handlers.event_handler import EventHandler
from app.events.schemas.domain_event import DomainEvent
from app.events.schemas.event_execution_log import EventExecutionLog


class EventBus:
    """In-memory publish/subscribe hub. No external broker, no persistence of its own
    — every subscriber lives only as long as this process does. This is the *only*
    thing modules are allowed to depend on to react to what another module did;
    nothing should ever import another module's engine/service just to trigger it.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._execution_logs: list[EventExecutionLog] = []

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._subscribers[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        handlers = self._subscribers.get(event_name, [])
        if handler not in handlers:
            raise HandlerNotSubscribedError(event_name, handler)
        handlers.remove(handler)

    async def publish(self, event: DomainEvent) -> list[EventExecutionLog]:
        """Publish one event and run every subscriber for it. Returns the execution
        logs produced by this one publish() call (also kept in list_execution_logs())."""
        return await self.dispatch(event)

    async def publish_many(self, events: list[DomainEvent]) -> list[EventExecutionLog]:
        logs: list[EventExecutionLog] = []
        for event in events:
            logs.extend(await self.publish(event))
        return logs

    async def dispatch(self, event: DomainEvent) -> list[EventExecutionLog]:
        """Runs every handler subscribed to `event.event_name`, in subscription order.
        A handler raising never stops the others, and never propagates out of here —
        see EventExecutionLog for how failures surface instead.
        """
        logs: list[EventExecutionLog] = []
        for handler in list(self._subscribers.get(event.event_name, [])):
            log = await self._run_handler(handler, event)
            logs.append(log)
            self._execution_logs.append(log)
        return logs

    @staticmethod
    async def _run_handler(handler: EventHandler, event: DomainEvent) -> EventExecutionLog:
        start = time.perf_counter()
        try:
            await handler.handle(event)
            success, error = True, None
        except Exception as exc:  # a subscriber's failure must never break the bus
            success, error = False, str(exc)
        return EventExecutionLog(
            event_id=event.event_id,
            event_name=event.event_name,
            handler=handler.__class__.__name__,
            execution_time=time.perf_counter() - start,
            success=success,
            error=error,
        )

    def list_execution_logs(self) -> list[EventExecutionLog]:
        return list(self._execution_logs)

    def subscriber_count(self, event_name: str) -> int:
        return len(self._subscribers.get(event_name, []))
