from decimal import Decimal
from typing import Sequence

from app.application.workspaces.mission.mission_workspace_metrics import MissionWorkspaceMetrics
from app.application.workspaces.mission.mission_workspace_summary import MissionWorkspaceSummary
from app.models.mission.mission import Mission
from app.models.mission.mission_event import MissionEvent
from app.models.mission.mission_metrics import MissionMetrics
from app.models.prospecting.prospect import Prospect
from app.outreach.models.enums import MessageStatus
from app.outreach.models.outreach_asset import OutreachAsset
from app.sales_intelligence.models.recommendation import Recommendation
from app.sales_intelligence.schemas.analysis_result import AnalysisResult
from app.schemas.mission.enums import PipelineHealth
from app.schemas.mission.mission import MissionRead
from app.schemas.mission.mission_event import MissionEventRead
from app.schemas.prospecting.prospect import ProspectRead


class MissionWorkspaceMapper:
    """Turns domain entities already fetched by MissionWorkspaceService into
    Workspace DTOs. Pure shape transformation — every value here already exists
    somewhere; nothing is computed, scored, or persisted.
    """

    @staticmethod
    def to_mission_read(mission: Mission) -> MissionRead:
        return MissionRead.model_validate(mission)

    @staticmethod
    def to_prospect_reads(prospects: Sequence[Prospect]) -> list[ProspectRead]:
        return [ProspectRead.model_validate(prospect) for prospect in prospects]

    @staticmethod
    def to_timeline(events: Sequence[MissionEvent]) -> list[MissionEventRead]:
        return [MissionEventRead.model_validate(event) for event in events]

    @staticmethod
    def to_summary(mission: Mission, health: PipelineHealth | None) -> MissionWorkspaceSummary:
        return MissionWorkspaceSummary(
            mission_name=mission.name,
            status=mission.status,
            progress=mission.progress or 0,
            health=health,
            started_at=mission.started_at,
            finished_at=mission.finished_at,
            owner=mission.owner_id,
        )

    @staticmethod
    def to_metrics(
        metrics: MissionMetrics | None,
        *,
        fallback_companies_found: int,
        fallback_prospects: int,
        assets: Sequence[OutreachAsset],
    ) -> MissionWorkspaceMetrics:
        pending = sum(1 for asset in assets if asset.status == MessageStatus.PENDING_APPROVAL)
        return MissionWorkspaceMetrics(
            companies_found=metrics.companies_found if metrics else fallback_companies_found,
            qualified=metrics.companies_qualified if metrics else 0,
            prospects=metrics.prospects_created if metrics else fallback_prospects,
            assets_generated=len(assets),
            assets_pending=pending,
            meetings=metrics.meetings if metrics else 0,
            contracts=metrics.contracts if metrics else 0,
            conversion_rate=metrics.conversion_rate if metrics else None,
            estimated_revenue=Decimal(metrics.won_value) if metrics else Decimal("0"),
        )

    @staticmethod
    def to_recommendations(analyses: Sequence[AnalysisResult]) -> list[Recommendation]:
        recommendations: list[Recommendation] = []
        for analysis in analyses:
            recommendations.extend(analysis.recommendations)
        return recommendations
