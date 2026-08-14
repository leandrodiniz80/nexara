from pydantic import BaseModel, ConfigDict

from app.platform.lifecycle.lifecycle_manager import LifecycleManager
from app.platform.lifecycle.lifecycle_participant import LifecycleParticipant


class LifecycleStopper(BaseModel):
    """The platform's official infrastructure for stopping
    LifecycleParticipants — a frozen model holding exactly one
    collaborator. `stop_all()` walks `manager.participants()` in order,
    calls `stop()` on each, and returns exactly those participants back
    in the same order. No exception handling, no filtering, no
    deduplication, and no additional logic of any kind.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    manager: LifecycleManager

    def stop_all(self) -> tuple[LifecycleParticipant, ...]:
        participants = self.manager.participants()
        for participant in participants:
            participant.stop()
        return tuple(participants)
