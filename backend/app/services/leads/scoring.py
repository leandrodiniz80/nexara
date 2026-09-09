from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.leads.automation_activity_log import AutomationActivityLog
from app.models.leads.lead import Lead
from app.models.leads.lead_activity_log import LeadActivityLog
from app.schemas.leads.lead import LeadResponse, ScoreBreakdownItem
from app.services.leads.enrichment import (
    ACTION_FIRST_CONTACT,
    ACTION_FOLLOW_UP,
    ACTION_URGENT_FOLLOW_UP,
    COMPANY_SIZE_PT,
    COMPANY_SIZE_SCORE_IMPACT,
    HIGH_VALUE_INDUSTRIES,
    INDUSTRY_PT,
    LARGE_COMPANY_SIZES,
    generate_lead_message_by_action,
)

# "Recent" for the automation-activity boost — same window LeadResponse's
# other "recent" concepts (e.g. GET /leads/attention's default
# stale_after_days) use in this codebase. Also reused as the manual-activity
# ("Recent manual activity" breakdown line) window — one cutoff, one query,
# shared by both.
_RECENT_AUTOMATION_DAYS = 3
# "Task completed in the last 24h" breakdown line's own window — deliberately
# tighter than the 3-day manual-activity window above, since this one is
# specifically about celebrating a *just-finished* task, not general recent
# touch.
_RECENT_TASK_COMPLETION_HOURS = 24


def compute_next_best_action(lead: Lead, *, is_overdue: bool) -> str | None:
    """"What should I do about this lead right now" — a plain rule table on
    status (+ overdue), no ML/LLM involved. Converted (and any other status
    outside new/contacted, e.g. lost) has nothing left to act on. Builds on
    ACTION_FIRST_CONTACT/ACTION_URGENT_FOLLOW_UP/ACTION_FOLLOW_UP
    (enrichment.py) rather than its own string literals, since
    generate_lead_message_by_action() matches on those same prefixes to
    pick a message tone for suggested_message."""
    if lead.status == "new":
        action = ACTION_FIRST_CONTACT
    elif lead.status == "contacted":
        action = ACTION_URGENT_FOLLOW_UP if is_overdue else ACTION_FOLLOW_UP
    else:
        return None

    if lead.enrichment_data:
        industry = INDUSTRY_PT.get(lead.enrichment_data.get("industry", ""))
        size = COMPANY_SIZE_PT.get(lead.enrichment_data.get("company_size", ""))
        if industry and size:
            action += f" com empresa de {industry} de {size}"

    return action


def compute_lead_score(
    lead: Lead,
    *,
    has_recent_automation: bool,
    has_recent_manual_activity: bool,
    task_completed_recently: bool,
    now: datetime,
) -> tuple[int, list[ScoreBreakdownItem]]:
    """Dynamic score, computed at read time from the lead's current state —
    never persisted (Lead.score, the stored column, is only this
    computation's starting baseline). Pure: no DB access, so a batch of
    leads can share one query for each of the three things this needs
    beyond the lead row itself (has_recent_automation,
    has_recent_manual_activity, task_completed_recently) — see
    score_leads() below.

    converted leads short-circuit to 100 outright ("score máximo"), no
    other factor considered. Every other status accumulates deltas on top
    of the stored baseline, clamped to [0, 100].

    The "act today or lose it" reinforcement layer (workday command-mode
    round) is deliberately additive on top of the pre-existing overdue/idle
    checks below, not a replacement for them: an overdue, long-idle lead now
    stacks both its original penalty and this layer's, dropping toward 0
    faster than before. That's intentional — the whole point of this layer
    is to make neglect cost visibly more than before."""
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

    if days_idle > 7:
        stale_impact = -25
        breakdown.append(
            ScoreBreakdownItem(reason="Idle for over a week — re-engage today", impact=stale_impact)
        )
        total += stale_impact

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

        action_impact = -20
        breakdown.append(
            ScoreBreakdownItem(reason="Task overdue — act today", impact=action_impact)
        )
        total += action_impact

    if has_recent_automation:
        automation_impact = 10
        breakdown.append(
            ScoreBreakdownItem(reason="Recent automation activity", impact=automation_impact)
        )
        total += automation_impact

    if has_recent_manual_activity:
        manual_activity_impact = 10
        breakdown.append(
            ScoreBreakdownItem(reason="Recent manual activity", impact=manual_activity_impact)
        )
        total += manual_activity_impact

    if task_completed_recently:
        completion_impact = 15
        breakdown.append(
            ScoreBreakdownItem(reason="Task completed in the last 24h", impact=completion_impact)
        )
        total += completion_impact

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

        revenue_impact = COMPANY_SIZE_SCORE_IMPACT.get(company_size, 0)
        if revenue_impact:
            breakdown.append(
                ScoreBreakdownItem(reason="High revenue potential", impact=revenue_impact)
            )
            total += revenue_impact
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
    before this. Exactly two extra queries total (recent automation
    activity, recent manual activity) for the whole batch, regardless of
    how many leads are passed in — no N+1."""
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

    # One query covers both "Recent manual activity" (any event, 3-day
    # window — same cutoff as automation's, above) and "Task completed in
    # the last 24h" (task_completed events only, tighter window) — both
    # booleans are derived from this same result set in Python instead of
    # querying twice.
    manual_activity_stmt = select(
        LeadActivityLog.lead_id, LeadActivityLog.event_type, LeadActivityLog.created_at
    ).where(
        LeadActivityLog.lead_id.in_(lead_ids),
        LeadActivityLog.created_at >= cutoff,
    )
    manual_activity_rows = (await db.execute(manual_activity_stmt)).all()
    recent_manual_activity_ids = {row.lead_id for row in manual_activity_rows}

    task_completion_cutoff = now - timedelta(hours=_RECENT_TASK_COMPLETION_HOURS)
    recent_task_completed_ids = {
        row.lead_id
        for row in manual_activity_rows
        if row.event_type == "task_completed" and row.created_at >= task_completion_cutoff
    }

    responses = []
    for lead in leads:
        score, breakdown = compute_lead_score(
            lead,
            has_recent_automation=lead.id in recent_lead_ids,
            has_recent_manual_activity=lead.id in recent_manual_activity_ids,
            task_completed_recently=lead.id in recent_task_completed_ids,
            now=now,
        )
        is_overdue = lead.next_action_due_at is not None and lead.next_action_due_at < now
        days_overdue = (now - lead.next_action_due_at).days if is_overdue else None

        next_best_action = compute_next_best_action(lead, is_overdue=is_overdue)
        suggested_message = (
            generate_lead_message_by_action(lead, next_best_action, lead.owner_email or "the team")
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


# Candidate-pool size for rank_leads_by_priority() — same value and rationale
# as GET /leads/priority's own docstring: comfortably above any realistic
# per-org lead count at this product stage.
_PRIORITY_CANDIDATE_POOL_SIZE = 200


async def rank_leads_by_priority(db: AsyncSession, organization_id: str) -> list[LeadResponse]:
    """Same ranking as GET /leads/priority (overdue tasks first, then due
    today, then future-dated, then no next_action at all — score DESC
    within each bucket), factored out so the workday command-mode engine
    (get_next_actionable_lead(), workday_engine.py) can reuse it without a
    second, separately-maintained copy of the bucket logic. Deliberately
    duplicates GET /leads/priority's own inline implementation rather than
    having that endpoint call this — it's already shipped and working, and
    this round's mandate is zero regression on existing routes."""
    candidate_pool_stmt = (
        select(Lead)
        .where(
            Lead.organization_id == organization_id,
            Lead.deleted_at.is_(None),
            Lead.status != "converted",
        )
        .order_by(Lead.next_action_due_at.asc().nulls_last())
        .limit(_PRIORITY_CANDIDATE_POOL_SIZE)
    )
    candidates = (await db.execute(candidate_pool_stmt)).scalars().all()

    scored = await score_leads(db, candidates)
    now = datetime.now(timezone.utc)

    def bucket(response: LeadResponse) -> int:
        due = response.next_action_due_at
        if due is None:
            return 3
        if response.is_overdue:
            return 0
        return 1 if due.date() == now.date() else 2

    scored.sort(key=lambda response: (bucket(response), -response.score))
    return scored
