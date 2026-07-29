from app.models.mission.mission import Mission
from app.repositories.base import BaseRepository


class MissionRepository(BaseRepository[Mission]):
    model = Mission
