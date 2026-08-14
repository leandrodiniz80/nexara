from pydantic import BaseModel, ConfigDict

from app.platform.events.event_executor import PlatformEventExecutor


class PlatformEvents(BaseModel):
    """The platform's official public facade for its event subsystem — a
    frozen model holding exactly one collaborator. `events()` delegates
    exclusively to `executor.execute()` and returns exactly what it
    produced, fresh on every call. No additional logic, no
    transformation, no interpretation, no exception handling.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    executor: PlatformEventExecutor

    def events(self) -> tuple[object, ...]:
        return self.executor.execute()
