from pydantic import BaseModel, ConfigDict

from app.platform.lifecycle.lifecycle_participant import LifecycleParticipant
from app.platform.lifecycle.lifecycle_participant_registry import LifecycleParticipantRegistry


class LifecycleManager(BaseModel):
    """An intermediate layer over LifecycleParticipantRegistry — a frozen
    model holding exactly one collaborator. It never starts or stops a
    participant, never caches or memoizes anything itself: every method
    is a direct, single-line delegation to `registry`, nothing more.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    registry: LifecycleParticipantRegistry

    def participant(self, name: str) -> LifecycleParticipant | None:
        return self.registry.find(name)

    def exists(self, name: str) -> bool:
        return self.registry.exists(name)

    def participants(self) -> list[LifecycleParticipant]:
        return self.registry.list()
