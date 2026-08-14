import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.mission.enums import MissionStatus
from app.schemas.mission.enums import PipelineHealth


class MissionWorkspaceSummary(BaseModel):
    """The header-card view of a Mission — everything a Workspace screen shows
    above the fold, before the caller scrolls into metrics/timeline/prospects."""

    mission_name: str
    status: MissionStatus
    progress: int
    health: PipelineHealth | None
    started_at: datetime | None
    finished_at: datetime | None
    owner: uuid.UUID | None
