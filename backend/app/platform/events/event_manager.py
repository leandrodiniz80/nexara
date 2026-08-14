from pydantic import BaseModel, ConfigDict

from app.platform.events.event_registry import EventRegistry
from app.platform.events.platform_event import PlatformEvent


class PlatformEventManager(BaseModel):
    """An intermediate layer over EventRegistry — a frozen model holding
    exactly one collaborator. It never runs or transforms an event, and
    never caches or memoizes anything itself: every method is a direct,
    single-line delegation to `registry`, nothing more.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    registry: EventRegistry

    def event(self, name: str) -> PlatformEvent | None:
        return self.registry.find(name)

    def exists(self, name: str) -> bool:
        return self.registry.exists(name)

    def events(self) -> list[PlatformEvent]:
        return self.registry.list()
