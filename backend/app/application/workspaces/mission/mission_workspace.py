from datetime import datetime

from pydantic import BaseModel, Field

from app.application.workspaces.mission.mission_workspace_metrics import MissionWorkspaceMetrics
from app.jobs.models.job import Job
from app.outreach.models.outreach_asset import OutreachAsset
from app.sales_intelligence.models.recommendation import Recommendation
from app.schemas.mission.enums import PipelineHealth
from app.schemas.mission.mission import MissionRead
from app.schemas.mission.mission_event import MissionEventRead
from app.schemas.prospecting.prospect import ProspectRead


class MissionWorkspace(BaseModel):
    """Everything a Mission's workspace screen needs to render, assembled from
    already-persisted data across Mission, Job, Prospecting, Research, Sales
    Intelligence and Outreach — no domain logic, no recalculation. This is the one
    shape a future Frontend/API layer depends on instead of six different domains.
    """

    mission: MissionRead
    job: Job | None
    statistics: MissionWorkspaceMetrics
    progress: int
    timeline: list[MissionEventRead] = Field(default_factory=list)
    prospects: list[ProspectRead] = Field(default_factory=list)
    assets: list[OutreachAsset] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    last_execution: datetime | None
    health: PipelineHealth | None
