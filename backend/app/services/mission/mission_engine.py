import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.models.mission.enums import MissionPriority, MissionStatus
from app.models.mission.mission import Mission
from app.models.mission.mission_metrics import MissionMetrics
from app.models.prospecting.enums import ProspectStage, ProspectStatus
from app.repositories.base import actor_kwargs
from app.repositories.mission.mission_metrics_repository import MissionMetricsRepository
from app.repositories.mission.mission_repository import MissionRepository
from app.repositories.prospecting.prospect_repository import ProspectRepository
from app.schemas.mission.enums import PipelineHealth
from app.schemas.mission.mission_summary import MissionSummary
from app.services.mission.exceptions import InvalidMissionTransitionError
from app.services.mission.mission_timeline import MissionTimeline

_MEETING_OR_LATER_STAGES = {
    ProspectStage.MEETING,
    ProspectStage.PROPOSAL,
    ProspectStage.NEGOTIATION,
    ProspectStage.WON,
}
_PROPOSAL_OR_LATER_STAGES = {ProspectStage.PROPOSAL, ProspectStage.NEGOTIATION, ProspectStage.WON}


class MissionEngine:
    """Domain module owning the Mission lifecycle (open -> running -> paused/resumed ->
    finished/cancelled) and the metrics/progress/forecast/summary derived from the
    Campaigns and Prospects that belong to it.
    """

    def __init__(
        self,
        repository: MissionRepository,
        metrics_repository: MissionMetricsRepository,
        prospect_repository: ProspectRepository,
        timeline: MissionTimeline,
    ) -> None:
        self.repository = repository
        self.metrics_repository = metrics_repository
        self.prospect_repository = prospect_repository
        self.timeline = timeline

    async def create(
        self,
        *,
        name: str,
        description: str | None = None,
        objective: str | None = None,
        priority: MissionPriority = MissionPriority.NORMAL,
        target_segment: str | None = None,
        target_region: str | None = None,
        target_city: str | None = None,
        target_state: str | None = None,
        target_quantity: int | None = None,
        target_meetings: int | None = None,
        target_contracts: int | None = None,
        target_revenue: Decimal | None = None,
        deadline: date | None = None,
        owner_id: uuid.UUID | None = None,
        created_by: uuid.UUID | None = None,
    ) -> Mission:
        mission = await self.repository.create(
            name=name,
            description=description,
            objective=objective,
            status=MissionStatus.DRAFT,
            priority=priority,
            target_segment=target_segment,
            target_region=target_region,
            target_city=target_city,
            target_state=target_state,
            target_quantity=target_quantity,
            target_meetings=target_meetings,
            target_contracts=target_contracts,
            target_revenue=target_revenue,
            deadline=deadline,
            owner_id=owner_id,
            progress=0,
            created_by=created_by,
            updated_by=created_by,
        )
        await self.metrics_repository.create(
            mission_id=mission.id, created_by=created_by, updated_by=created_by
        )
        await self.timeline.record(
            mission.id,
            "mission_created",
            description=f"Missão '{mission.name}' criada.",
            created_by=created_by,
        )
        return mission

    @staticmethod
    def _ensure_status(mission: Mission, allowed: set[MissionStatus], action: str) -> None:
        if mission.status not in allowed:
            raise InvalidMissionTransitionError(mission.id, mission.status, action)

    async def start(self, mission: Mission, *, updated_by: uuid.UUID | None = None) -> Mission:
        self._ensure_status(mission, {MissionStatus.DRAFT, MissionStatus.PLANNING}, "start")
        mission = await self.repository.update(
            mission,
            status=MissionStatus.RUNNING,
            started_at=mission.started_at or datetime.now(timezone.utc),
            **actor_kwargs(updated_by),
        )
        await self.timeline.record(
            mission.id, "mission_started", description="Missão iniciada.", created_by=updated_by
        )
        return mission

    async def pause(
        self, mission: Mission, *, reason: str | None = None, updated_by: uuid.UUID | None = None
    ) -> Mission:
        self._ensure_status(mission, {MissionStatus.RUNNING}, "pause")
        mission = await self.repository.update(
            mission, status=MissionStatus.PAUSED, **actor_kwargs(updated_by)
        )
        await self.timeline.record(
            mission.id, "mission_paused", description=reason or "Missão pausada.", created_by=updated_by
        )
        return mission

    async def resume(self, mission: Mission, *, updated_by: uuid.UUID | None = None) -> Mission:
        self._ensure_status(mission, {MissionStatus.PAUSED}, "resume")
        mission = await self.repository.update(
            mission, status=MissionStatus.RUNNING, **actor_kwargs(updated_by)
        )
        await self.timeline.record(
            mission.id, "mission_resumed", description="Missão retomada.", created_by=updated_by
        )
        return mission

    async def finish(self, mission: Mission, *, updated_by: uuid.UUID | None = None) -> Mission:
        self._ensure_status(mission, {MissionStatus.RUNNING, MissionStatus.PAUSED}, "finish")
        mission = await self.repository.update(
            mission,
            status=MissionStatus.FINISHED,
            finished_at=datetime.now(timezone.utc),
            progress=100,
            **actor_kwargs(updated_by),
        )
        await self.timeline.record(
            mission.id, "mission_finished", description="Missão finalizada.", created_by=updated_by
        )
        return mission

    async def cancel(
        self, mission: Mission, *, reason: str | None = None, updated_by: uuid.UUID | None = None
    ) -> Mission:
        self._ensure_status(
            mission,
            {MissionStatus.DRAFT, MissionStatus.PLANNING, MissionStatus.RUNNING, MissionStatus.PAUSED},
            "cancel",
        )
        mission = await self.repository.update(
            mission,
            status=MissionStatus.CANCELLED,
            finished_at=datetime.now(timezone.utc),
            **actor_kwargs(updated_by),
        )
        await self.timeline.record(
            mission.id, "mission_cancelled", description=reason or "Missão cancelada.", created_by=updated_by
        )
        return mission

    async def _get_or_create_metrics(self, mission_id: uuid.UUID) -> MissionMetrics:
        metrics = await self.metrics_repository.get_by_mission(mission_id)
        if metrics is None:
            metrics = await self.metrics_repository.create(mission_id=mission_id)
        return metrics

    async def calculate_metrics(self, mission: Mission) -> MissionMetrics:
        """Recomputes everything derivable from Prospect data today (companies found/
        qualified, prospects, meetings, proposals, contracts, won/lost value) and the
        rates. The email-funnel counters (generated/approved/sent/opened/replied) are
        left untouched — see MissionMetrics' docstring for why — but their *rates* are
        recomputed from whatever values are currently stored in them.
        """
        metrics = await self._get_or_create_metrics(mission.id)
        prospects = await self.prospect_repository.list_by_mission(mission.id)

        companies_found = len({p.company_id for p in prospects})
        companies_qualified = len({p.company_id for p in prospects if p.qualified_at is not None})
        prospects_created = len(prospects)
        meetings = sum(1 for p in prospects if p.current_stage in _MEETING_OR_LATER_STAGES)
        proposals = sum(1 for p in prospects if p.current_stage in _PROPOSAL_OR_LATER_STAGES)
        contracts = sum(1 for p in prospects if p.status == ProspectStatus.WON)
        won_value = sum(
            (p.estimated_value or Decimal("0")) for p in prospects if p.status == ProspectStatus.WON
        )
        lost_value = sum(
            (p.estimated_value or Decimal("0")) for p in prospects if p.status == ProspectStatus.LOST
        )

        conversion_rate = round((contracts / prospects_created) * 100, 2) if prospects_created else None
        response_rate = (
            round((metrics.emails_replied / metrics.emails_sent) * 100, 2) if metrics.emails_sent else None
        )
        meeting_rate = round((meetings / prospects_created) * 100, 2) if prospects_created else None

        return await self.metrics_repository.update(
            metrics,
            companies_found=companies_found,
            companies_qualified=companies_qualified,
            prospects_created=prospects_created,
            meetings=meetings,
            proposals=proposals,
            contracts=contracts,
            won_value=won_value,
            lost_value=lost_value,
            conversion_rate=conversion_rate,
            response_rate=response_rate,
            meeting_rate=meeting_rate,
        )

    async def calculate_progress(self, mission: Mission) -> int:
        """Average of whichever targets are actually set (quantity/meetings/contracts/
        revenue), each capped at 100%. 0 if the mission has no targets at all."""
        metrics = await self.calculate_metrics(mission)
        fractions: list[float] = []
        if mission.target_quantity:
            fractions.append(min(1.0, metrics.prospects_created / mission.target_quantity))
        if mission.target_meetings:
            fractions.append(min(1.0, metrics.meetings / mission.target_meetings))
        if mission.target_contracts:
            fractions.append(min(1.0, metrics.contracts / mission.target_contracts))
        if mission.target_revenue:
            fractions.append(min(1.0, float(metrics.won_value) / float(mission.target_revenue)))

        progress = round((sum(fractions) / len(fractions)) * 100) if fractions else 0
        await self.repository.update(mission, progress=progress)
        return progress

    async def forecast_completion(self, mission: Mission) -> date | None:
        """Projects a completion date from the mission's pace so far (prospects created
        per day since started_at) against target_quantity. None when there isn't enough
        information yet (not started, no quantity target, or no prospects created).

        Reads the persisted MissionMetrics snapshot rather than recomputing it — call
        calculate_metrics()/calculate_progress() first if prospects may have changed
        since the snapshot was last refreshed.
        """
        if mission.started_at is None or not mission.target_quantity:
            return None
        metrics = await self._get_or_create_metrics(mission.id)
        if metrics.prospects_created <= 0:
            return None
        elapsed_days = max(1, (datetime.now(timezone.utc) - mission.started_at).days)
        daily_rate = metrics.prospects_created / elapsed_days
        if daily_rate <= 0:
            return None
        remaining = max(0, mission.target_quantity - metrics.prospects_created)
        days_needed = remaining / daily_rate
        estimated = (datetime.now(timezone.utc) + timedelta(days=days_needed)).date()
        await self.repository.update(mission, estimated_completion=estimated)
        return estimated

    def _assess_pipeline_health(
        self, mission: Mission, progress: int, days_remaining: int | None
    ) -> PipelineHealth:
        if mission.deadline is None:
            return PipelineHealth.HEALTHY if progress >= 50 else PipelineHealth.AT_RISK

        total_days = (mission.deadline - mission.created_at.date()).days
        if total_days <= 0:
            return PipelineHealth.HEALTHY if progress >= 100 else PipelineHealth.CRITICAL

        elapsed_days = total_days - (days_remaining or 0)
        expected_progress = min(100, max(0, round((elapsed_days / total_days) * 100)))
        gap = expected_progress - progress
        if gap <= 10:
            return PipelineHealth.HEALTHY
        if gap <= 30:
            return PipelineHealth.AT_RISK
        return PipelineHealth.CRITICAL

    def _recommend_next_action(self, metrics: MissionMetrics, pipeline_health: PipelineHealth) -> str:
        if metrics.prospects_created == 0:
            return "Nenhum prospect criado ainda — inicie a pesquisa de empresas para esta missão."
        if metrics.companies_qualified == 0:
            return "Nenhuma empresa qualificada ainda — revise os prospects abertos."
        if metrics.meetings == 0:
            return "Ainda sem reuniões agendadas — priorize follow-ups nos prospects qualificados."
        if pipeline_health == PipelineHealth.CRITICAL:
            return "Missão em risco de não bater a meta no prazo — aumente o volume de prospecção."
        if pipeline_health == PipelineHealth.AT_RISK:
            return "Ritmo abaixo do esperado — considere priorizar os prospects mais quentes."
        return "Pipeline saudável — manter o ritmo atual de prospecção e follow-ups."

    async def summary(self, mission: Mission) -> MissionSummary:
        progress = await self.calculate_progress(mission)
        metrics = await self._get_or_create_metrics(mission.id)
        days_remaining = (mission.deadline - date.today()).days if mission.deadline else None
        pipeline_health = self._assess_pipeline_health(mission, progress, days_remaining)
        next_action = self._recommend_next_action(metrics, pipeline_health)

        prospects = await self.prospect_repository.list_by_mission(mission.id)
        weighted_pipeline = sum(
            (p.estimated_value or Decimal("0")) * Decimal(p.probability or 0) / Decimal(100)
            for p in prospects
            if p.status == ProspectStatus.OPEN
        )
        estimated_revenue = Decimal(metrics.won_value) + weighted_pipeline

        return MissionSummary(
            status=mission.status,
            progress=progress,
            days_remaining=days_remaining,
            total_prospects=metrics.prospects_created,
            qualified=metrics.companies_qualified,
            meetings=metrics.meetings,
            contracts=metrics.contracts,
            estimated_revenue=estimated_revenue,
            pipeline_health=pipeline_health,
            next_recommended_action=next_action,
        )
