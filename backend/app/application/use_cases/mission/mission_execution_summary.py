from pydantic import BaseModel, Field

from app.jobs.models.job import Job
from app.schemas.mission.mission import MissionRead


class MissionExecutionSummary(BaseModel):
    """What one CreateProspectingMissionUseCase run produced — the counters a caller
    checks first, before digging into `prospects`/`assets` on the full Response."""

    mission: MissionRead
    job: Job
    companies_found: int
    qualified: int
    prospects_created: int
    assets_generated: int
    assets_pending_approval: int
    execution_time: float
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
