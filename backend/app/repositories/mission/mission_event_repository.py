import uuid
from typing import Sequence

from sqlalchemy import select

from app.models.mission.mission_event import MissionEvent
from app.repositories.base import BaseRepository


class MissionEventRepository(BaseRepository[MissionEvent]):
    model = MissionEvent

    async def list_by_mission(self, mission_id: uuid.UUID) -> Sequence[MissionEvent]:
        stmt = (
            select(MissionEvent)
            .where(MissionEvent.mission_id == mission_id, MissionEvent.deleted_at.is_(None))
            .order_by(MissionEvent.occurred_at.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
