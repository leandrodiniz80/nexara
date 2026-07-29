from abc import ABC, abstractmethod
from typing import ClassVar

from app.events.schemas.domain_event import DomainEvent


class EventHandler(ABC):
    """Reacts to one kind of event. Never called directly by application code — only
    ever invoked by EventBus.dispatch(), which is what lets modules react to each
    other's events without importing each other.
    """

    event_name: ClassVar[str]

    @abstractmethod
    async def handle(self, event: DomainEvent) -> None:
        """React to `event`. Raising here is safe: EventBus.dispatch() catches it,
        logs it in an EventExecutionLog, and keeps calling the other subscribers."""
