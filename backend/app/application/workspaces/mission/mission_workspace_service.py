import uuid
from datetime import date, datetime
from typing import Sequence

from app.application.workspaces.mission.mission_workspace import MissionWorkspace
from app.application.workspaces.mission.mission_workspace_mapper import MissionWorkspaceMapper
from app.application.workspaces.mission.mission_workspace_metrics import MissionWorkspaceMetrics
from app.application.workspaces.mission.mission_workspace_query import MissionWorkspaceQuery
from app.application.workspaces.mission.mission_workspace_summary import MissionWorkspaceSummary
from app.jobs.models.job import Job
from app.jobs.repositories.job_repository import JobRepository
from app.models.mission.mission import Mission
from app.models.prospecting.prospect import Prospect
from app.outreach.models.outreach_asset import OutreachAsset
from app.outreach.repositories.outreach_asset_repository import OutreachAssetRepository
from app.repositories.mission.mission_event_repository import MissionEventRepository
from app.repositories.mission.mission_metrics_repository import MissionMetricsRepository
from app.repositories.mission.mission_repository import MissionRepository
from app.repositories.prospecting.interaction_repository import InteractionRepository
from app.repositories.prospecting.prospect_repository import ProspectRepository
from app.research.repositories.research_result_repository import ResearchResultRepository
from app.sales_intelligence.models.recommendation import Recommendation
from app.sales_intelligence.repositories.sales_intelligence_repository import (
    SalesIntelligenceRepository,
)
from app.schemas.mission.enums import PipelineHealth
from app.schemas.mission.mission_event import MissionEventRead

_GAP_HEALTHY_THRESHOLD = 10
_GAP_AT_RISK_THRESHOLD = 30


def _classify_health(mission: Mission) -> PipelineHealth | None:
    """A read-only, view-layer categorization from *already-stored* mission.progress
    and mission.deadline — never recalculates progress itself. Mirrors the same
    thresholds MissionEngine._assess_pipeline_health() uses (that method is private
    and recalculates progress first, so it isn't called from here), kept as its own
    small function rather than a shared one so this layer never has a runtime
    dependency on MissionEngine's internals. PipelineHealth is documented as "a
    view-layer concept, never persisted" — computing it for display is exactly what
    it's for.
    """
    progress = mission.progress or 0
    if mission.deadline is None:
        return PipelineHealth.HEALTHY if progress >= 50 else PipelineHealth.AT_RISK

    total_days = (mission.deadline - mission.created_at.date()).days
    if total_days <= 0:
        return PipelineHealth.HEALTHY if progress >= 100 else PipelineHealth.CRITICAL

    days_remaining = (mission.deadline - date.today()).days
    elapsed_days = total_days - days_remaining
    expected_progress = min(100, max(0, round((elapsed_days / total_days) * 100)))
    gap = expected_progress - progress
    if gap <= _GAP_HEALTHY_THRESHOLD:
        return PipelineHealth.HEALTHY
    if gap <= _GAP_AT_RISK_THRESHOLD:
        return PipelineHealth.AT_RISK
    return PipelineHealth.CRITICAL


class MissionWorkspaceService:
    """Consults every repository a Mission Workspace needs and hands the results to
    MissionWorkspaceMapper. No scores, no metrics, no progress are recalculated here
    — everything returned is exactly what was already persisted, or a straightforward
    read-only aggregation over already-persisted rows (counting OutreachAssets,
    picking the most recent Job, taking the max of two timestamps).
    """

    def __init__(
        self,
        mission_repository: MissionRepository,
        mission_metrics_repository: MissionMetricsRepository,
        mission_event_repository: MissionEventRepository,
        job_repository: JobRepository,
        prospect_repository: ProspectRepository,
        research_result_repository: ResearchResultRepository,
        sales_intelligence_repository: SalesIntelligenceRepository,
        outreach_asset_repository: OutreachAssetRepository,
        interaction_repository: InteractionRepository,
        mapper: MissionWorkspaceMapper | None = None,
    ) -> None:
        self.mission_repository = mission_repository
        self.mission_metrics_repository = mission_metrics_repository
        self.mission_event_repository = mission_event_repository
        self.job_repository = job_repository
        self.prospect_repository = prospect_repository
        self.research_result_repository = research_result_repository
        self.sales_intelligence_repository = sales_intelligence_repository
        self.outreach_asset_repository = outreach_asset_repository
        self.interaction_repository = interaction_repository
        self.mapper = mapper or MissionWorkspaceMapper()

    async def load(self, query: MissionWorkspaceQuery) -> MissionWorkspace | None:
        mission = await self.mission_repository.get_by_id(query.mission_id)
        if mission is None:
            return None

        summary = await self.build_summary(mission)
        metrics = await self.build_metrics(mission)
        timeline = await self.build_timeline(mission.id)
        recommendations = await self.build_recommendations(mission.id)

        prospects = await self.prospect_repository.list_by_mission(mission.id)
        assets = await self._collect_assets(prospects)
        job = self._latest_job(mission.id)

        return MissionWorkspace(
            mission=self.mapper.to_mission_read(mission),
            job=job,
            statistics=metrics,
            progress=mission.progress or 0,
            timeline=timeline,
            prospects=self.mapper.to_prospect_reads(prospects),
            assets=list(assets),
            recommendations=recommendations,
            last_execution=await self._last_execution(job, prospects),
            health=summary.health,
        )

    async def build_summary(self, mission: Mission) -> MissionWorkspaceSummary:
        return self.mapper.to_summary(mission, _classify_health(mission))

    async def build_metrics(self, mission: Mission) -> MissionWorkspaceMetrics:
        metrics = await self.mission_metrics_repository.get_by_mission(mission.id)
        prospects = await self.prospect_repository.list_by_mission(mission.id)
        assets = await self._collect_assets(prospects)
        fallback_companies_found = len(
            self.research_result_repository.list_by_city(mission.target_city or "")
        )
        return self.mapper.to_metrics(
            metrics,
            fallback_companies_found=fallback_companies_found,
            fallback_prospects=len(prospects),
            assets=assets,
        )

    async def build_timeline(self, mission_id: uuid.UUID) -> list[MissionEventRead]:
        events = await self.mission_event_repository.list_by_mission(mission_id)
        return self.mapper.to_timeline(events)

    async def build_recommendations(self, mission_id: uuid.UUID) -> list[Recommendation]:
        prospects = await self.prospect_repository.list_by_mission(mission_id)
        analyses = []
        for prospect in prospects:
            analysis = self.sales_intelligence_repository.get(prospect.company_id)
            if analysis is not None:
                analyses.append(analysis)
        return self.mapper.to_recommendations(analyses)

    async def _collect_assets(self, prospects: Sequence[Prospect]) -> list[OutreachAsset]:
        assets: list[OutreachAsset] = []
        for prospect in prospects:
            assets.extend(self.outreach_asset_repository.list_by_prospect(prospect.id))
        return assets

    def _latest_job(self, mission_id: uuid.UUID) -> Job | None:
        jobs = [job for job in self.job_repository.list_all() if job.mission_id == mission_id]
        return jobs[-1] if jobs else None

    async def _last_execution(
        self, job: Job | None, prospects: Sequence[Prospect]
    ) -> datetime | None:
        """When did anything last happen on this mission — the latest of the last
        Job's timestamps and the most recent Interaction across its prospects."""
        candidates: list[datetime] = []
        if job is not None:
            if job.finished_at is not None:
                candidates.append(job.finished_at)
            if job.started_at is not None:
                candidates.append(job.started_at)
        for prospect in prospects:
            interactions = await self.interaction_repository.list_by_prospect(prospect.id)
            candidates.extend(interaction.occurred_at for interaction in interactions)
        return max(candidates) if candidates else None
