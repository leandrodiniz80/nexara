import uuid

from app.models.mission.enums import MissionStatus


class MissionDomainError(Exception):
    """Base class for Mission Engine business-rule violations."""


class InvalidMissionTransitionError(MissionDomainError):
    """Raised when a lifecycle method is called from a MissionStatus it doesn't allow
    (e.g. pause() on a mission that isn't RUNNING)."""

    def __init__(self, mission_id: uuid.UUID, current_status: MissionStatus, action: str) -> None:
        self.mission_id = mission_id
        self.current_status = current_status
        self.action = action
        super().__init__(
            f"Cannot {action} mission {mission_id}: it is '{current_status.value}'."
        )
