from pydantic import BaseModel, ConfigDict

from app.platform.events.event_manager import PlatformEventManager


class PlatformEventExecutor(BaseModel):
    """The platform's official infrastructure for running the registered
    PlatformEvents — a frozen model holding exactly one collaborator.
    `execute()` walks `manager.events()` in order, calls `payload()` on
    each, and returns those results as a tuple in the same order. No
    exception handling, no filtering, no interpretation of the results.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    manager: PlatformEventManager

    def execute(self) -> tuple[object, ...]:
        events = self.manager.events()
        return tuple(event.payload() for event in events)
