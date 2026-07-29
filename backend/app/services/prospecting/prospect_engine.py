import uuid
from datetime import datetime, timezone
from decimal import Decimal

from app.models.prospecting.enums import (
    InteractionType,
    ProspectOrigin,
    ProspectPriority,
    ProspectStage,
    ProspectStatus,
    ProspectTemperature,
)
from app.models.prospecting.interaction import Interaction
from app.models.prospecting.prospect import Prospect
from app.repositories.base import actor_kwargs
from app.repositories.prospecting.campaign_repository import CampaignRepository
from app.repositories.prospecting.interaction_repository import InteractionRepository
from app.repositories.prospecting.prospect_repository import ProspectRepository
from app.services.prospecting.exceptions import (
    CampaignNotFoundError,
    ProspectClosedError,
    ProspectDomainError,
)

# Funnel order used to derive a stage's contribution to calculate_score(). WON/LOST are
# terminal and handled separately (max/zero points), so they are excluded from the ramp.
_STAGE_ORDER = [
    ProspectStage.NEW,
    ProspectStage.RESEARCHING,
    ProspectStage.QUALIFIED,
    ProspectStage.CONTACT_READY,
    ProspectStage.EMAIL_PENDING_APPROVAL,
    ProspectStage.EMAIL_SENT,
    ProspectStage.FOLLOW_UP,
    ProspectStage.RESPONDED,
    ProspectStage.MEETING,
    ProspectStage.PROPOSAL,
    ProspectStage.NEGOTIATION,
]
_STAGE_MAX_POINTS = 40
_TEMPERATURE_WEIGHTS = {
    ProspectTemperature.COLD: 0,
    ProspectTemperature.WARM: 15,
    ProspectTemperature.HOT: 30,
}
_PRIORITY_WEIGHTS = {
    ProspectPriority.LOW: 0,
    ProspectPriority.NORMAL: 5,
    ProspectPriority.HIGH: 10,
    ProspectPriority.URGENT: 15,
}
_STAGES_CLOSED_BY_DEDICATED_METHODS = {ProspectStage.WON, ProspectStage.LOST}


def _stage_weight(stage: ProspectStage) -> int:
    if stage == ProspectStage.WON:
        return _STAGE_MAX_POINTS
    if stage == ProspectStage.LOST:
        return 0
    try:
        position = _STAGE_ORDER.index(stage)
    except ValueError:
        return 0
    return round(position / (len(_STAGE_ORDER) - 1) * _STAGE_MAX_POINTS)


def _recency_weight(last_interaction_at: datetime | None) -> int:
    if last_interaction_at is None:
        return 0
    delta_days = (datetime.now(timezone.utc) - last_interaction_at).days
    if delta_days <= 7:
        return 15
    if delta_days <= 30:
        return 8
    return 0


class ProspectEngine:
    """Domain module owning the Prospect lifecycle: opening, qualifying, scoring,
    staging, closing (won/lost) and the interaction trail that drives it.

    All writes go through `ProspectRepository`/`InteractionRepository`, which flush but
    do not commit — committing the transaction is the caller's (future API layer's)
    responsibility, consistent with the rest of the repository layer.
    """

    def __init__(
        self,
        repository: ProspectRepository,
        interaction_repository: InteractionRepository,
        campaign_repository: CampaignRepository,
    ) -> None:
        self.repository = repository
        self.interaction_repository = interaction_repository
        self.campaign_repository = campaign_repository

    @staticmethod
    def _ensure_open(prospect: Prospect) -> None:
        if prospect.status != ProspectStatus.OPEN:
            raise ProspectClosedError(prospect.id, prospect.status)

    async def create_prospect(
        self,
        *,
        company_id: uuid.UUID,
        campaign_id: uuid.UUID,
        owner_id: uuid.UUID | None = None,
        origin: ProspectOrigin | None = None,
        priority: ProspectPriority = ProspectPriority.NORMAL,
        estimated_value: Decimal | None = None,
        probability: int | None = None,
        notes: str | None = None,
        created_by: uuid.UUID | None = None,
    ) -> Prospect:
        """Open a new opportunity for a company on a campaign, in stage NEW.

        mission_id is deliberately not a parameter here: a Prospect must belong to the
        same Mission as its Campaign, so it is always derived from `campaign.mission_id`
        rather than trusted from the caller — this makes the (Prospect.mission_id ==
        Prospect.campaign.mission_id) invariant impossible to violate by construction,
        since there is no database-level way to check across two tables with a CHECK
        constraint.
        """
        campaign = await self.campaign_repository.get_by_id(campaign_id)
        if campaign is None:
            raise CampaignNotFoundError(campaign_id)

        return await self.repository.create(
            company_id=company_id,
            campaign_id=campaign_id,
            mission_id=campaign.mission_id,
            owner_id=owner_id,
            origin=origin,
            priority=priority,
            estimated_value=estimated_value,
            probability=probability,
            notes=notes,
            status=ProspectStatus.OPEN,
            temperature=ProspectTemperature.COLD,
            current_stage=ProspectStage.NEW,
            created_by=created_by,
            updated_by=created_by,
        )

    async def qualify(self, prospect: Prospect, *, updated_by: uuid.UUID | None = None) -> Prospect:
        """Move an open prospect into QUALIFIED, stamping qualified_at once (idempotent)."""
        self._ensure_open(prospect)
        return await self.repository.update(
            prospect,
            current_stage=ProspectStage.QUALIFIED,
            qualified_at=prospect.qualified_at or datetime.now(timezone.utc),
            **actor_kwargs(updated_by),
        )

    async def disqualify(
        self, prospect: Prospect, *, reason: str | None = None, updated_by: uuid.UUID | None = None
    ) -> Prospect:
        """Close an open prospect as DISQUALIFIED (never met basic fit criteria).

        Distinct from mark_as_lost(): disqualification happens before a real sales
        cycle started, so current_stage is left as-is rather than forced to LOST.
        """
        self._ensure_open(prospect)
        return await self.repository.update(
            prospect,
            status=ProspectStatus.DISQUALIFIED,
            reason_lost=reason,
            **actor_kwargs(updated_by),
        )

    async def change_stage(
        self, prospect: Prospect, new_stage: ProspectStage, *, updated_by: uuid.UUID | None = None
    ) -> Prospect:
        """Move an open prospect to any non-terminal funnel stage.

        WON/LOST must go through mark_as_won()/mark_as_lost(): those also flip `status`
        and stamp the closing timestamp atomically, so current_stage and status can
        never drift out of sync with each other.
        """
        self._ensure_open(prospect)
        if new_stage in _STAGES_CLOSED_BY_DEDICATED_METHODS:
            raise ProspectDomainError(
                "Use mark_as_won()/mark_as_lost() to close a prospect, not change_stage()."
            )
        update_kwargs: dict = {"current_stage": new_stage, **actor_kwargs(updated_by)}
        if new_stage == ProspectStage.QUALIFIED and prospect.qualified_at is None:
            update_kwargs["qualified_at"] = datetime.now(timezone.utc)
        return await self.repository.update(prospect, **update_kwargs)

    async def calculate_score(self, prospect: Prospect) -> int:
        """Deterministic 0-100 heuristic: funnel progress (40) + temperature (30) +
        priority (15) + recency of the last interaction (15). Persists the result."""
        score = (
            _stage_weight(prospect.current_stage)
            + _TEMPERATURE_WEIGHTS.get(prospect.temperature, 0)
            + _PRIORITY_WEIGHTS.get(prospect.priority, 0)
            + _recency_weight(prospect.last_interaction_at)
        )
        score = max(0, min(100, score))
        await self.repository.update(prospect, score=score)
        return score

    async def mark_as_won(self, prospect: Prospect, *, updated_by: uuid.UUID | None = None) -> Prospect:
        self._ensure_open(prospect)
        return await self.repository.update(
            prospect,
            status=ProspectStatus.WON,
            current_stage=ProspectStage.WON,
            converted_at=datetime.now(timezone.utc),
            **actor_kwargs(updated_by),
        )

    async def mark_as_lost(
        self, prospect: Prospect, *, reason: str | None = None, updated_by: uuid.UUID | None = None
    ) -> Prospect:
        self._ensure_open(prospect)
        return await self.repository.update(
            prospect,
            status=ProspectStatus.LOST,
            current_stage=ProspectStage.LOST,
            lost_at=datetime.now(timezone.utc),
            reason_lost=reason,
            **actor_kwargs(updated_by),
        )

    async def schedule_followup(
        self, prospect: Prospect, next_action_at: datetime, *, updated_by: uuid.UUID | None = None
    ) -> Prospect:
        self._ensure_open(prospect)
        return await self.repository.update(
            prospect, next_action_at=next_action_at, **actor_kwargs(updated_by)
        )

    async def register_interaction(
        self,
        prospect: Prospect,
        *,
        type: InteractionType,
        occurred_at: datetime | None = None,
        contact_id: uuid.UUID | None = None,
        notes: str | None = None,
        result: str | None = None,
        next_follow_up_at: datetime | None = None,
        created_by: uuid.UUID | None = None,
    ) -> Interaction:
        """Log a touchpoint and roll its timing into the prospect (last_interaction_at,
        and next_action_at when a follow-up date is given)."""
        occurred_at = occurred_at or datetime.now(timezone.utc)
        interaction = await self.interaction_repository.create(
            prospect_id=prospect.id,
            contact_id=contact_id,
            type=type,
            notes=notes,
            occurred_at=occurred_at,
            result=result,
            next_follow_up_at=next_follow_up_at,
            created_by=created_by,
            updated_by=created_by,
        )
        update_kwargs: dict = {"last_interaction_at": occurred_at, **actor_kwargs(created_by)}
        if next_follow_up_at is not None:
            update_kwargs["next_action_at"] = next_follow_up_at
        await self.repository.update(prospect, **update_kwargs)
        return interaction

    async def list_pipeline(
        self, *, owner_id: uuid.UUID | None = None, limit: int = 50, offset: int = 0
    ):
        return await self.repository.list_pipeline(owner_id=owner_id, limit=limit, offset=offset)

    async def list_by_stage(self, stage: ProspectStage, *, limit: int = 50, offset: int = 0):
        return await self.repository.list_by_stage(stage, limit=limit, offset=offset)

    async def list_by_campaign(self, campaign_id: uuid.UUID, *, limit: int = 50, offset: int = 0):
        return await self.repository.list_by_campaign(campaign_id, limit=limit, offset=offset)

    async def list_by_owner(self, owner_id: uuid.UUID, *, limit: int = 50, offset: int = 0):
        return await self.repository.list_by_owner(owner_id, limit=limit, offset=offset)

    async def search(
        self,
        *,
        query: str | None = None,
        stage: ProspectStage | None = None,
        status: ProspectStatus | None = None,
        temperature: ProspectTemperature | None = None,
        priority: ProspectPriority | None = None,
        campaign_id: uuid.UUID | None = None,
        owner_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ):
        return await self.repository.search(
            query=query,
            stage=stage,
            status=status,
            temperature=temperature,
            priority=priority,
            campaign_id=campaign_id,
            owner_id=owner_id,
            limit=limit,
            offset=offset,
        )
