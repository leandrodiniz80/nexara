from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.leads.automation_activity_log import AutomationActivityLog
from app.models.leads.lead import Lead
from app.schemas.leads.lead import LeadResponse, ScoreBreakdownItem

# "Recent" for the automation-activity boost — same window LeadResponse's
# other "recent" concepts (e.g. GET /leads/attention's default
# stale_after_days) use in this codebase.
_RECENT_AUTOMATION_DAYS = 3


def compute_lead_score(
    lead: Lead, *, has_recent_automation: bool, now: datetime
) -> tuple[int, list[ScoreBreakdownItem]]:
    """Dynamic score, computed at read time from the lead's current state —
    never persisted (Lead.score, the stored column, is only this
    computation's starting baseline). Pure: no DB access, so a batch of
    leads can share one query for the one thing this needs beyond the lead
    row itself (has_recent_automation) — see score_leads() below.

    converted leads short-circuit to 100 outright ("score máximo"), no
    other factor considered. Every other status accumulates deltas on top
    of the stored baseline, clamped to [0, 100]."""
    if lead.status == "converted":
        impact = 100 - lead.score
        return 100, [ScoreBreakdownItem(reason="Lead converted", impact=impact)]

    breakdown: list[ScoreBreakdownItem] = []
    total = lead.score

    days_idle = (now - lead.updated_at).days
    if days_idle >= 14:
        recency_impact = -30
    elif days_idle >= 7:
        recency_impact = -20
    elif days_idle >= 3:
        recency_impact = -10
    else:
        recency_impact = 0
    if recency_impact:
        breakdown.append(
            ScoreBreakdownItem(reason=f"No activity in {days_idle} days", impact=recency_impact)
        )
    total += recency_impact

    if lead.status == "contacted" and days_idle >= 3:
        contacted_impact = -15
        breakdown.append(
            ScoreBreakdownItem(
                reason="Contacted with no recent follow-up", impact=contacted_impact
            )
        )
        total += contacted_impact

    if lead.next_action_due_at is not None and lead.next_action_due_at < now:
        overdue_impact = -30
        label = f"Overdue task: {lead.next_action}" if lead.next_action else "Overdue task"
        breakdown.append(ScoreBreakdownItem(reason=label, impact=overdue_impact))
        total += overdue_impact

    if has_recent_automation:
        automation_impact = 10
        breakdown.append(
            ScoreBreakdownItem(reason="Recent automation activity", impact=automation_impact)
        )
        total += automation_impact

    return max(0, min(100, total)), breakdown


async def score_leads(db: AsyncSession, leads: list[Lead]) -> list[LeadResponse]:
    """Builds LeadResponse for each lead with score/score_breakdown
    overridden by compute_lead_score(), instead of the plain
    LeadResponse.model_validate(lead) every lead-returning endpoint used
    before this. Exactly one extra query total (recent automation activity
    for the whole batch), regardless of how many leads are passed in."""
    if not leads:
        return []

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=_RECENT_AUTOMATION_DAYS)
    lead_ids = [lead.id for lead in leads]

    recent_stmt = (
        select(AutomationActivityLog.lead_id)
        .distinct()
        .where(
            AutomationActivityLog.lead_id.in_(lead_ids),
            AutomationActivityLog.created_at >= cutoff,
        )
    )
    recent_lead_ids = set((await db.execute(recent_stmt)).scalars().all())

    responses = []
    for lead in leads:
        score, breakdown = compute_lead_score(
            lead, has_recent_automation=lead.id in recent_lead_ids, now=now
        )
        response = LeadResponse.model_validate(lead)
        responses.append(response.model_copy(update={"score": score, "score_breakdown": breakdown}))
    return responses
