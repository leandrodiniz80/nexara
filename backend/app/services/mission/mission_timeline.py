import uuid
from datetime import datetime, timezone
from typing import Any, Sequence

from app.models.mission.mission_event import MissionEvent
from app.repositories.mission.mission_event_repository import MissionEventRepository


class MissionTimeline:
    """Domain-facing API over a Mission's MissionEvent rows.

    MissionEvent is the persisted row (model/schema/repository); MissionTimeline is what
    callers actually use to record and read a mission's history — MissionEngine calls
    `record()` on every lifecycle transition, and any future integration (a campaign
    being created, a prospect converting, an email going out) can call it the same way
    without needing to know how events are stored.
    """

    def __init__(self, event_repository: MissionEventRepository) -> None:
        self.event_repository = event_repository

    async def record(
        self,
        mission_id: uuid.UUID,
        event: str,
        *,
        description: str | None = None,
        event_metadata: dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
        created_by: uuid.UUID | None = None,
    ) -> MissionEvent:
        return await self.event_repository.create(
            mission_id=mission_id,
            event=event,
            description=description,
            event_metadata=event_metadata,
            occurred_at=occurred_at or datetime.now(timezone.utc),
            created_by=created_by,
            updated_by=created_by,
        )

    async def list_timeline(self, mission_id: uuid.UUID) -> Sequence[MissionEvent]:
        return await self.event_repository.list_by_mission(mission_id)
