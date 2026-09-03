from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.leads.automation_activity_log import AutomationActivityLog
from app.models.leads.lead import Lead
from app.schemas.leads.lead import LeadResponse, ScoreBreakdownItem
from app.services.leads.enrichment import (
    HIGH_VALUE_INDUSTRIES,
    LARGE_COMPANY_SIZES,
    generate_first_contact_message,
)

# "Recent" for the automation-activity boost — same window LeadResponse's
# other "recent" concepts (e.g. GET /leads/attention's default
# stale_after_days) use in this codebase.
_RECENT_AUTOMATION_DAYS = 3

# Portuguese labels for next_best_action's enrichment context fragment (e.g.
# "Fazer follow-up urgente com empresa de tecnologia de médio porte") — keyed
# on enrichment.py's own _INDUSTRIES/_COMPANY_SIZES values, so an unrecognized
# value (there shouldn't be one) just omits the context instead of raising.
_INDUSTRY_PT = {
    "Technology": "tecnologia",
    "Finance": "finanças",
    "Healthcare": "saúde",
    "Retail": "varejo",
    "Manufacturing": "indústria",
    "Education": "educação",
    "Real Estate": "imóveis",
    "Hospitality": "hospitalidade",
}
_COMPANY_SIZE_PT = {
    "1-10": "pequeno porte",
    "11-50": "pequeno porte",
    "51-200": "médio porte",
    "201-500": "médio porte",
    "500+": "grande porte",
}


def compute_next_best_action(lead: Lead, *, is_overdue: bool) -> str | None:
    """"What should I do about this lead right now" — a plain rule table on
    status (+ overdue), no ML/LLM involved. Converted (and any other status
    outside new/contacted, e.g. lost) has nothing left to act on."""
    if lead.status == "new":
        action = "Fazer primeiro contato"
    elif lead.status == "contacted":
        action = "Fazer follow-up urgente" if is_overdue else "Acompanhar lead"
    else:
        return None

    if lead.enrichment_data:
        industry = _INDUSTRY_PT.get(lead.enrichment_data.get("industry", ""))
        size = _COMPANY_SIZE_PT.get(lead.enrichment_data.get("company_size", ""))
        if industry and size:
            action += f" com empresa de {industry} de {size}"

    return action


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

    if (now - lead.created_at).total_seconds() < 3600:
        fresh_impact = 15
        breakdown.append(
            ScoreBreakdownItem(reason="New lead — fresh opportunity", impact=fresh_impact)
        )
        total += fresh_impact

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

    if lead.enrichment_data:
        industry = lead.enrichment_data.get("industry")
        if industry in HIGH_VALUE_INDUSTRIES:
            industry_impact = 10
            breakdown.append(
                ScoreBreakdownItem(reason=f"High-value sector: {industry}", impact=industry_impact)
            )
            total += industry_impact

        company_size = lead.enrichment_data.get("company_size")
        if company_size in LARGE_COMPANY_SIZES:
            size_impact = 10
            breakdown.append(
                ScoreBreakdownItem(
                    reason=f"Larger company: {company_size} employees", impact=size_impact
                )
            )
            total += size_impact
    else:
        unenriched_impact = -5
        breakdown.append(
            ScoreBreakdownItem(reason="Lead not yet enriched", impact=unenriched_impact)
        )
        total += unenriched_impact

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
        is_overdue = lead.next_action_due_at is not None and lead.next_action_due_at < now
        days_overdue = (now - lead.next_action_due_at).days if is_overdue else None

        next_best_action = compute_next_best_action(lead, is_overdue=is_overdue)
        suggested_message = (
            generate_first_contact_message(lead, lead.owner_email or "the team")
            if next_best_action is not None and settings.AI_ENABLED
            else None
        )

        response = LeadResponse.model_validate(lead)
        responses.append(
            response.model_copy(
                update={
                    "score": score,
                    "score_breakdown": breakdown,
                    "is_overdue": is_overdue,
                    "days_overdue": days_overdue,
                    "next_best_action": next_best_action,
                    "suggested_message": suggested_message,
                }
            )
        )
    return responses
