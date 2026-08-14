from pydantic import BaseModel, ConfigDict, Field

from app.platform.lifecycle.lifecycle_participant import LifecycleParticipant
from app.shared.registry.registry import Registry


class LifecycleParticipantRegistry(BaseModel):
    """The platform's frozen registry of LifecycleParticipants — pure
    lookup, nothing else: it never starts or stops a participant, never
    knows any concrete participant's domain, and never mutates in place.
    Implemented exclusively by encapsulating a generic
    Registry[LifecycleParticipant] — no reimplementation of
    register/register_many/find/exists/list. Participants are identified
    by their class name, since LifecycleParticipant itself defines no
    naming contract.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    participants: tuple[LifecycleParticipant, ...] = Field(default_factory=tuple)

    def _as_registry(self) -> Registry[LifecycleParticipant]:
        return Registry(
            items=self.participants, key=lambda participant: type(participant).__name__
        )

    def register(self, participant: LifecycleParticipant) -> "LifecycleParticipantRegistry":
        return LifecycleParticipantRegistry(
            participants=tuple(self._as_registry().register(participant).list())
        )

    def register_many(
        self, participants: list[LifecycleParticipant]
    ) -> "LifecycleParticipantRegistry":
        return LifecycleParticipantRegistry(
            participants=tuple(self._as_registry().register_many(participants).list())
        )

    def find(self, name: str) -> LifecycleParticipant | None:
        return self._as_registry().find(name)

    def exists(self, name: str) -> bool:
        return self._as_registry().exists(name)

    def list(self) -> list[LifecycleParticipant]:
        return self._as_registry().list()
