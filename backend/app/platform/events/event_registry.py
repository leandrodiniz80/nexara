from pydantic import BaseModel, ConfigDict, Field

from app.platform.events.platform_event import PlatformEvent
from app.shared.registry.registry import Registry


class EventRegistry(BaseModel):
    """The platform's frozen registry of PlatformEvents — pure lookup,
    nothing else: it never dispatches or executes an event, never knows
    any concrete event's domain, and never mutates in place. Implemented
    exclusively by encapsulating a generic Registry[PlatformEvent] — no
    reimplementation of register/register_many/find/exists/list.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    events: tuple[PlatformEvent, ...] = Field(default_factory=tuple)

    def _as_registry(self) -> Registry[PlatformEvent]:
        return Registry(items=self.events, key=lambda event: event.name())

    def register(self, event: PlatformEvent) -> "EventRegistry":
        return EventRegistry(events=tuple(self._as_registry().register(event).list()))

    def register_many(self, events: list[PlatformEvent]) -> "EventRegistry":
        return EventRegistry(
            events=tuple(self._as_registry().register_many(events).list())
        )

    def find(self, name: str) -> PlatformEvent | None:
        return self._as_registry().find(name)

    def exists(self, name: str) -> bool:
        return self._as_registry().exists(name)

    def list(self) -> list[PlatformEvent]:
        return self._as_registry().list()
