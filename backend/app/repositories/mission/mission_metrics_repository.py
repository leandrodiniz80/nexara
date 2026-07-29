import uuid

from sqlalchemy import select

from app.models.mission.mission_metrics import MissionMetrics
from app.repositories.base import BaseRepository


class MissionMetricsRepository(BaseRepository[MissionMetrics]):
    model = MissionMetrics

    async def get_by_mission(self, mission_id: uuid.UUID) -> MissionMetrics | None:
        stmt = select(MissionMetrics).where(
            MissionMetrics.mission_id == mission_id, MissionMetrics.deleted_at.is_(None)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
