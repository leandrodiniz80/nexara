from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.leads.automation_activity_log import AutomationActivityLog
from app.models.leads.lead import Lead
from app.models.leads.lead_activity_log import LeadActivityLog
from app.schemas.leads.lead import (
    ConversionInsightsResponse,
    LeadResponse,
    ResponseMetricsResponse,
    ScoreBreakdownItem,
)
from app.services.leads.enrichment import (
    ACTION_CLOSE_DEAL,
    ACTION_FIRST_CONTACT,
    ACTION_FOLLOW_UP,
    ACTION_MAXIMUM_URGENCY_FOLLOW_UP,
    ACTION_NURTURE_OR_DISCARD,
    ACTION_URGENT_FOLLOW_UP,
    COMPANY_SIZE_PT,
    COMPANY_SIZE_SCORE_IMPACT,
    HIGH_VALUE_INDUSTRIES,
    HIGH_VALUE_LEAD_THRESHOLD,
    INDUSTRY_PT,
    LARGE_COMPANY_SIZES,
    format_brl,
    generate_lead_message_by_action,
    get_lead_estimated_value,
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
# compute_win_probability()'s "no activity" penalty threshold — same 7-day
# window compute_lead_score's own "Idle for over a week" line already uses.
_WIN_PROBABILITY_IDLE_DAYS = 7
# score_breakdown's "High conversion probability" line only appears at this
# threshold — matches the frontend's own green-badge cutoff (lead-card.tsx),
# so the same lead reads as "high probability" in both places.
_HIGH_WIN_PROBABILITY_THRESHOLD = 70
# Reinforcement bonus compute_lead_score() adds to `score` when
# win_probability clears the threshold above — same magnitude as this
# codebase's other secondary signals (Recent automation activity,
# High-value sector, Larger company all use +10 too).
_HIGH_WIN_PROBABILITY_SCORE_BONUS = 10
# compute_next_best_action()'s "low probability" cutoff (feedback-loop
# round) — same <40 red-badge threshold the frontend's own
# getWinProbabilityVariant (lead-card.tsx) already uses, so a lead reading
# as "red" there is exactly the one nurture-or-discard picks out here.
_LOW_WIN_PROBABILITY_THRESHOLD = 40
# compute_lead_score()'s "no activity" cutoff for the smart follow-up
# escalation penalty (feedback-loop round) — deliberately > (not >=) the
# existing "Contacted with no recent follow-up" line's own 3-day cutoff
# just below, so day 3 gets the original mild warning and day 4+ stacks
# this harsher one on top, same "layers stack additively" precedent this
# function's own docstring already documents for the overdue/idle lines.
_FOLLOW_UP_ESCALATION_IDLE_DAYS = 3
# compute_deal_risk()'s idle-days cutoffs (AI Deal Coach round). CRITICAL's
# is deliberately higher than HIGH/MEDIUM's — a big deal has to be *further*
# gone before it's the worst bucket, since CRITICAL is also reachable via
# is_overdue alone (no idle-days floor at all) for a high-value lead.
_DEAL_RISK_CRITICAL_IDLE_DAYS = 5
_DEAL_RISK_HIGH_IDLE_DAYS = 3
_DEAL_RISK_MEDIUM_IDLE_DAYS = 3
# compute_deal_risk()'s HIGH-tier win_probability floor — the prompt's own
# number, deliberately distinct from _HIGH_WIN_PROBABILITY_THRESHOLD (70):
# that one gates a score bonus for an already-good sign, this one gates
# "worth the alarm" for a stalling deal that still looks winnable.
_DEAL_RISK_HIGH_WIN_PROBABILITY = 60

# compute_lead_score()'s adaptive-scoring bonuses (feedback-loop round) —
# rewarding a lead that matches the org's own real-world highest-converting
# profile (compute_conversion_insights()). Industry counts for more than
# company size since it's historically the stronger conversion signal in
# this codebase's own high-value groupings (HIGH_VALUE_INDUSTRIES already
# outweighs LARGE_COMPANY_SIZES the same way in compute_lead_score's
# existing enrichment section: +10 vs. the size line's own smaller
# contribution).
_CONVERSION_PROFILE_INDUSTRY_BONUS = 10
_CONVERSION_PROFILE_COMPANY_SIZE_BONUS = 8

# Feedback-loop-of-outcomes round — maps a LeadActivityLog event_type to the
# lead_response_state it represents (LeadResponse/scoring.py's own "derived,
# no migration" field — see that model's own docstring). "message_sent" is
# deliberately absent: it's what response_time_minutes is timed *from*, not
# a response state itself.
RESPONSE_STATE_BY_EVENT_TYPE = {
    "lead_responded": "responded",
    "lead_interested": "interested",
    "lead_rejected": "not_interested",
}
# The reverse of the mapping above — POST /leads/{id}/record-response
# (leads.py) uses this to turn its own request body's `response` back into
# the event_type it logs, so the two directions can't drift out of sync.
RESPONSE_EVENT_TYPE_BY_STATE = {state: event_type for event_type, state in RESPONSE_STATE_BY_EVENT_TYPE.items()}
# compute_response_metrics()'s reporting window — the prompt's own number,
# a stable-enough sample without going stale the way an all-time rate would
# as messaging habits/segments shift.
_RESPONSE_METRICS_WINDOW_DAYS = 30
# compute_lead_score()'s response-outcome bonuses/penalty — a real "the
# market told us" signal, so both outweigh every purely-behavioral line
# above (the biggest of which is -30, matched here so a rejection is never
# a *smaller* deal than "task overdue").
_INTERESTED_SCORE_BONUS = 25
_NOT_INTERESTED_SCORE_PENALTY = -30
# compute_lead_score()'s "matches the org's best-responding segment" bonus
# — same magnitude as the feedback-loop round's own adaptive-scoring
# industry bonus (_CONVERSION_PROFILE_INDUSTRY_BONUS), since this is the
# same kind of learned-not-hardcoded signal, just for response rate instead
# of conversion.
_RESPONSE_SEGMENT_BONUS = 10


def compute_win_probability(
    lead: Lead, *, has_recent_manual_activity: bool, task_completed_recently: bool, now: datetime
) -> int:
    """0-100 estimated likelihood this lead converts — a plain rule table
    over status plus the same recent-activity/overdue/enrichment signals
    compute_lead_score() already gathers for its own batch query, no
    ML/LLM. converted/lost short-circuit to 100/0 outright, matching
    those statuses' own compute_lead_score treatment. is_overdue/days_idle
    are recomputed here rather than threaded through as params — same
    "cheap, pure, independently derived" precedent score_leads() already
    sets by computing its own is_overdue separately from
    compute_lead_score's internal check."""
    if lead.status == "converted":
        return 100
    if lead.status == "lost":
        return 0

    probability = 40 if lead.status == "contacted" else 20  # "new"

    if has_recent_manual_activity:
        probability += 15
    if task_completed_recently:
        probability += 10

    is_overdue = lead.next_action_due_at is not None and lead.next_action_due_at < now
    if is_overdue:
        probability -= 20

    days_idle = (now - lead.updated_at).days
    if days_idle > _WIN_PROBABILITY_IDLE_DAYS:
        probability -= 25

    if lead.enrichment_data:
        probability += 10
        if lead.enrichment_data.get("company_size") in LARGE_COMPANY_SIZES:
            probability += 10

    return max(0, min(100, probability))


def compute_next_best_action(
    lead: Lead, *, is_overdue: bool, now: datetime, win_probability: int
) -> str | None:
    """"What should I do about this lead right now" — a plain rule table on
    status (+ overdue), no ML/LLM involved. Converted (and any other status
    outside new/contacted, e.g. lost) has nothing left to act on. Builds on
    ACTION_FIRST_CONTACT/ACTION_URGENT_FOLLOW_UP/ACTION_FOLLOW_UP/
    ACTION_MAXIMUM_URGENCY_FOLLOW_UP/ACTION_CLOSE_DEAL/
    ACTION_NURTURE_OR_DISCARD (enrichment.py) rather than its own string
    literals, since generate_lead_message_by_action() matches on those same
    prefixes to pick a message tone for suggested_message.

    Next Best Action 2.0 (feedback-loop round): for a "contacted" lead,
    win_probability and days since last activity (recomputed here from
    lead.updated_at, same "cheap, pure, independently derived" precedent as
    compute_win_probability's own is_overdue/days_idle) now refine the plain
    overdue check into one ordered decision tree, highest-priority rule
    first:
      1. No activity in over _FOLLOW_UP_ESCALATION_IDLE_DAYS days — stop
         being passive, regardless of anything else (this is also
         compute_lead_score's -30 escalation-penalty trigger).
      2. Its next_action is overdue — the original urgent-follow-up case.
      3. High win_probability (and, by rule 1 not having fired, recent
         activity) — the deal is warm, go close it.
      4. Low win_probability — not worth aggressive chasing; nurture or
         let it go cold on its own.
      5. Otherwise — the original plain follow-up.
    """
    if lead.status == "new":
        action = ACTION_FIRST_CONTACT
    elif lead.status == "contacted":
        days_idle = (now - lead.updated_at).days
        if days_idle > _FOLLOW_UP_ESCALATION_IDLE_DAYS:
            action = ACTION_MAXIMUM_URGENCY_FOLLOW_UP
        elif is_overdue:
            action = ACTION_URGENT_FOLLOW_UP
        elif win_probability >= _HIGH_WIN_PROBABILITY_THRESHOLD:
            action = ACTION_CLOSE_DEAL
        elif win_probability < _LOW_WIN_PROBABILITY_THRESHOLD:
            action = ACTION_NURTURE_OR_DISCARD
        else:
            action = ACTION_FOLLOW_UP
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
    insights: ConversionInsightsResponse,
    lead_response_state: str,
    best_response_industry: str | None,
    now: datetime,
) -> tuple[int, list[ScoreBreakdownItem], int]:
    """Dynamic score, computed at read time from the lead's current state —
    never persisted (Lead.score, the stored column, is only this
    computation's starting baseline). Pure: no DB access, so a batch of
    leads can share one query for each of the things this needs beyond the
    lead row itself (has_recent_automation, has_recent_manual_activity,
    task_completed_recently, lead_response_state) plus the two org-wide
    aggregates (insights, best_response_industry) — see score_leads()
    below.

    converted leads short-circuit to 100 outright ("score máximo"), no
    other factor considered. Every other status accumulates deltas on top
    of the stored baseline, clamped to [0, 100].

    The "act today or lose it" reinforcement layer (workday command-mode
    round) is deliberately additive on top of the pre-existing overdue/idle
    checks below, not a replacement for them: an overdue, long-idle lead now
    stacks both its original penalty and this layer's, dropping toward 0
    faster than before. That's intentional — the whole point of this layer
    is to make neglect cost visibly more than before.

    Also returns win_probability (compute_win_probability()) as a third
    tuple element — computed here (not by a separate caller query) since it
    shares has_recent_manual_activity/task_completed_recently/now with this
    function already; a high win_probability also earns its own
    score_breakdown line (revenue-intelligence round), same "stack another
    reinforcement signal on top" precedent as the overdue/idle lines
    above."""
    if lead.status == "converted":
        impact = 100 - lead.score
        return 100, [ScoreBreakdownItem(reason="Lead converted", impact=impact)], 100

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

    # Smart follow-up escalation (feedback-loop round) — stacks on top of
    # the -15 line just above rather than replacing it, same "layers
    # compound, they don't override" precedent as the overdue lines below.
    if lead.status == "contacted" and days_idle > _FOLLOW_UP_ESCALATION_IDLE_DAYS:
        escalation_impact = -30
        breakdown.append(
            ScoreBreakdownItem(
                reason="Follow-up overdue — escalating to maximum urgency",
                impact=escalation_impact,
            )
        )
        total += escalation_impact

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

        # Adaptive scoring (feedback-loop round) — reward matching the
        # org's own real, learned highest-converting profile
        # (compute_conversion_insights()), on top of (not instead of) the
        # static high-value-industry/larger-company lines above, which
        # reward a fixed, hardcoded notion of "good" rather than a learned
        # one.
        if insights.best_industry and industry == insights.best_industry:
            profile_industry_impact = _CONVERSION_PROFILE_INDUSTRY_BONUS
            breakdown.append(
                ScoreBreakdownItem(
                    reason="Matches high-conversion profile: top-converting industry",
                    impact=profile_industry_impact,
                )
            )
            total += profile_industry_impact

        if insights.best_company_size and company_size == insights.best_company_size:
            profile_size_impact = _CONVERSION_PROFILE_COMPANY_SIZE_BONUS
            breakdown.append(
                ScoreBreakdownItem(
                    reason="Matches high-conversion profile: top-converting company size",
                    impact=profile_size_impact,
                )
            )
            total += profile_size_impact

        # Feedback-loop-of-outcomes round — same "learned, not hardcoded"
        # reward as the two lines above, but for response rate
        # (compute_response_metrics()) rather than conversion.
        if best_response_industry and industry == best_response_industry:
            segment_impact = _RESPONSE_SEGMENT_BONUS
            breakdown.append(
                ScoreBreakdownItem(
                    reason="Matches high-response segment", impact=segment_impact
                )
            )
            total += segment_impact
    else:
        unenriched_impact = -5
        breakdown.append(
            ScoreBreakdownItem(reason="Lead not yet enriched", impact=unenriched_impact)
        )
        total += unenriched_impact

    # Feedback-loop-of-outcomes round — a real "the market told us" signal,
    # not a proxy: outweighs every purely-behavioral line above, same
    # rationale as _INTERESTED_SCORE_BONUS/_NOT_INTERESTED_SCORE_PENALTY's
    # own docstring note.
    if lead_response_state == "interested":
        breakdown.append(
            ScoreBreakdownItem(
                reason="Lead responded and showed interest", impact=_INTERESTED_SCORE_BONUS
            )
        )
        total += _INTERESTED_SCORE_BONUS
    elif lead_response_state == "not_interested":
        breakdown.append(
            ScoreBreakdownItem(
                reason="Lead responded — not interested", impact=_NOT_INTERESTED_SCORE_PENALTY
            )
        )
        total += _NOT_INTERESTED_SCORE_PENALTY

    win_probability = compute_win_probability(
        lead,
        has_recent_manual_activity=has_recent_manual_activity,
        task_completed_recently=task_completed_recently,
        now=now,
    )
    if win_probability >= _HIGH_WIN_PROBABILITY_THRESHOLD:
        breakdown.append(
            ScoreBreakdownItem(
                reason="High conversion probability", impact=_HIGH_WIN_PROBABILITY_SCORE_BONUS
            )
        )
        total += _HIGH_WIN_PROBABILITY_SCORE_BONUS

    return max(0, min(100, total)), breakdown, win_probability


# Prefix compute_conversion_insights() writes into LeadActivityLog.message
# for a lost-lead outcome entry (see PATCH /leads/{id}/status, leads.py) and
# reads back to aggregate top_loss_reason. There's no metadata/JSONB column
# on LeadActivityLog to carry the reason as structured data (see that
# model's own docstring), so it's encoded in the message behind this fixed
# marker instead — the same "structured info via string matching" technique
# generate_lead_message_by_action() already uses for next_best_action.
LOSS_REASON_MARKER = "Motivo: "


async def compute_conversion_insights(
    db: AsyncSession, organization_id: str
) -> ConversionInsightsResponse:
    """Mines the org's own real outcomes for what actually converts — no
    ML, three plain aggregations over already-recorded data. Every field is
    None until there's enough real signal to say something, rather than a
    misleading default. Exactly two queries regardless of org size (a
    converted-leads row scan, an outcome-log row scan), same "one shared
    query per batch" precedent as score_leads()'s own two queries below —
    called once per score_leads() batch, not per lead.

    best_industry/best_company_size: the most frequent enrichment_data
    value among this org's *converted* leads — "what wins" isn't about
    every lead, only the ones that actually closed.

    avg_time_to_close_days/top_loss_reason: read from LeadActivityLog's
    "lead_won"/"lead_lost" outcome entries (PATCH /leads/{id}/status writes
    these — see leads.py), not LeadStatusHistory: the exact elapsed time is
    already captured per-event on duration_seconds at the moment of the
    transition, which is both simpler and more precise than re-deriving it
    from created_at/a status-history timestamp after the fact.
    """
    converted_stmt = select(Lead.enrichment_data).where(
        Lead.organization_id == organization_id,
        Lead.status == "converted",
        Lead.deleted_at.is_(None),
        Lead.enrichment_data.is_not(None),
    )
    converted_rows = (await db.execute(converted_stmt)).scalars().all()

    industry_counts: dict[str, int] = {}
    company_size_counts: dict[str, int] = {}
    for enrichment_data in converted_rows:
        industry = enrichment_data.get("industry")
        if industry:
            industry_counts[industry] = industry_counts.get(industry, 0) + 1
        company_size = enrichment_data.get("company_size")
        if company_size:
            company_size_counts[company_size] = company_size_counts.get(company_size, 0) + 1

    best_industry = max(industry_counts, key=industry_counts.get) if industry_counts else None
    best_company_size = (
        max(company_size_counts, key=company_size_counts.get) if company_size_counts else None
    )

    outcomes_stmt = select(
        LeadActivityLog.event_type, LeadActivityLog.message, LeadActivityLog.duration_seconds
    ).where(
        LeadActivityLog.organization_id == organization_id,
        LeadActivityLog.event_type.in_(["lead_won", "lead_lost"]),
    )
    outcome_rows = (await db.execute(outcomes_stmt)).all()

    close_days = [
        row.duration_seconds / 86400
        for row in outcome_rows
        if row.event_type == "lead_won" and row.duration_seconds is not None
    ]
    avg_time_to_close_days = round(sum(close_days) / len(close_days)) if close_days else None

    loss_reason_counts: dict[str, int] = {}
    for row in outcome_rows:
        if row.event_type != "lead_lost" or LOSS_REASON_MARKER not in row.message:
            continue
        reason = row.message.split(LOSS_REASON_MARKER, 1)[1].strip()
        if reason:
            loss_reason_counts[reason] = loss_reason_counts.get(reason, 0) + 1
    top_loss_reason = (
        max(loss_reason_counts, key=loss_reason_counts.get) if loss_reason_counts else None
    )

    return ConversionInsightsResponse(
        best_industry=best_industry,
        best_company_size=best_company_size,
        avg_time_to_close_days=avg_time_to_close_days,
        top_loss_reason=top_loss_reason,
    )


async def compute_response_metrics(
    db: AsyncSession, organization_id: str
) -> ResponseMetricsResponse:
    """Feedback-loop-of-outcomes round — org-wide messaging effectiveness
    mined from the last _RESPONSE_METRICS_WINDOW_DAYS of real outcomes, no
    ML. One query (message_sent/lead_responded/lead_interested/lead_rejected
    LeadActivityLog rows joined to their Lead for industry), aggregated in
    Python — same "one shared query per batch" precedent as
    compute_conversion_insights(). Every rate is 0.0 (not a misleading
    default like a stray None) when there's simply been nothing sent yet;
    avg_response_time_minutes/best_response_industry stay None in that
    case, same "None until there's real signal" rule
    ConversionInsightsResponse's own fields already follow.

    response_rate/interest_rate share the same denominator (messages sent),
    not compounding: interest_rate isn't "of those who responded, how many
    were interested" — it's "of everything sent, how many became
    interested," so the two read as directly comparable percentages of the
    same whole. Both can technically read above 100%: a single sent message
    can accumulate more than one response-type entry over time (e.g.
    "responded" today, "interested" logged later once that conversation
    develops), each counted here — a known approximation, same spirit as
    money_saved_today's own disclosed proxy (workday.py), not a strict
    one-to-one send/response ledger.

    best_response_industry is the industry with the highest per-industry
    response_rate among industries with at least one message sent — "what
    wins" here isn't about every message, only which segment is actually
    replying. Feeds compute_lead_score()'s "Matches high-response segment"
    bonus."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=_RESPONSE_METRICS_WINDOW_DAYS)
    rows_stmt = (
        select(LeadActivityLog.event_type, LeadActivityLog.duration_seconds, Lead.enrichment_data)
        .join(Lead, Lead.id == LeadActivityLog.lead_id)
        .where(
            LeadActivityLog.organization_id == organization_id,
            LeadActivityLog.event_type.in_(list(RESPONSE_STATE_BY_EVENT_TYPE) + ["message_sent"]),
            LeadActivityLog.created_at >= cutoff,
        )
    )
    rows = (await db.execute(rows_stmt)).all()

    sent_count = 0
    responded_count = 0
    interested_count = 0
    response_times_minutes: list[float] = []
    sent_by_industry: dict[str, int] = {}
    responded_by_industry: dict[str, int] = {}

    for row in rows:
        industry = row.enrichment_data.get("industry") if row.enrichment_data else None
        if row.event_type == "message_sent":
            sent_count += 1
            if industry:
                sent_by_industry[industry] = sent_by_industry.get(industry, 0) + 1
            continue

        responded_count += 1
        if industry:
            responded_by_industry[industry] = responded_by_industry.get(industry, 0) + 1
        if row.event_type == "lead_interested":
            interested_count += 1
        if row.duration_seconds is not None:
            response_times_minutes.append(row.duration_seconds / 60)

    response_rate = round(responded_count / sent_count * 100, 1) if sent_count else 0.0
    interest_rate = round(interested_count / sent_count * 100, 1) if sent_count else 0.0
    avg_response_time_minutes = (
        round(sum(response_times_minutes) / len(response_times_minutes), 1)
        if response_times_minutes
        else None
    )

    best_response_industry = (
        max(
            sent_by_industry,
            key=lambda industry: responded_by_industry.get(industry, 0) / sent_by_industry[industry],
        )
        if sent_by_industry
        else None
    )

    return ResponseMetricsResponse(
        response_rate=response_rate,
        interest_rate=interest_rate,
        avg_response_time_minutes=avg_response_time_minutes,
        best_response_industry=best_response_industry,
    )


def build_priority_reason(
    lead: Lead,
    *,
    estimated_value: int,
    win_probability: int,
    days_idle: int,
    is_overdue: bool,
) -> str:
    """"Why this lead?" (feedback-loop round) — one ready-to-render
    sentence explaining the same signals score_leads() already computed for
    this lead, composed from whichever of them are actually notable rather
    than always listing every factor. Pure/no DB access, same reasoning
    style as compute_next_best_action()."""
    if lead.status == "converted":
        return "Lead convertido — nada a fazer."
    if lead.status == "lost":
        return "Lead perdido — nada a fazer."

    clauses: list[str] = []
    if estimated_value >= HIGH_VALUE_LEAD_THRESHOLD:
        clauses.append(f"lead de alto valor (R$ {format_brl(estimated_value)})")
    if win_probability >= _HIGH_WIN_PROBABILITY_THRESHOLD:
        clauses.append(f"alta probabilidade ({win_probability}%)")
    elif win_probability < _LOW_WIN_PROBABILITY_THRESHOLD:
        clauses.append(f"baixa probabilidade ({win_probability}%)")
    if is_overdue:
        clauses.append("com tarefa atrasada")
    elif days_idle > _FOLLOW_UP_ESCALATION_IDLE_DAYS:
        clauses.append(f"sem atividade há {days_idle} dias")

    if not clauses:
        return "Lead em acompanhamento normal, sem sinais fortes de prioridade no momento."

    sentence = clauses[0] if len(clauses) == 1 else ", ".join(clauses[:-1]) + f" e {clauses[-1]}"
    return sentence[0].upper() + sentence[1:] + "."


def compute_deal_risk(
    lead: Lead, *, expected_value: int, win_probability: int, is_overdue: bool, now: datetime
) -> tuple[str, str]:
    """AI Deal Coach round — a plain rule table (no ML/external AI calls)
    collapsing money/probability/activity recency into one at-a-glance
    risk_level plus a short reason sentence. expected_value/win_probability
    aren't columns on Lead itself (they're computed earlier in the same
    score_leads() pass — compute_win_probability/get_lead_estimated_value),
    so they're passed in rather than recomputed here; idle_days is derived
    from lead.updated_at, same "cheap, pure, independently derived"
    precedent compute_win_probability's own is_overdue/days_idle already
    set. Converted/lost leads are always "low" — nothing left to lose, so
    nothing left to be at risk.

    Ordered highest-severity-first, same style as compute_next_best_action's
    own decision tree:
      CRITICAL: a big deal (>= HIGH_VALUE_LEAD_THRESHOLD) that's either
        overdue or idle for over _DEAL_RISK_CRITICAL_IDLE_DAYS.
      HIGH: a big deal that still looks winnable
        (win_probability >= _DEAL_RISK_HIGH_WIN_PROBABILITY) but idle for
        over _DEAL_RISK_HIGH_IDLE_DAYS.
      MEDIUM: idle for over _DEAL_RISK_MEDIUM_IDLE_DAYS, or overdue,
        regardless of value/probability — everything CRITICAL/HIGH didn't
        already catch.
      LOW: everything else.
    """
    if lead.status in ("converted", "lost"):
        return "low", "Lead já resolvido — nada em jogo."

    idle_days = (now - lead.updated_at).days
    is_big_deal = expected_value >= HIGH_VALUE_LEAD_THRESHOLD

    if is_big_deal and (is_overdue or idle_days > _DEAL_RISK_CRITICAL_IDLE_DAYS):
        cause = "com tarefa atrasada" if is_overdue else f"parado há {idle_days} dias"
        return "critical", (
            f"Negócio de R$ {format_brl(expected_value)} {cause} — risco de perda iminente."
        )

    if (
        is_big_deal
        and win_probability >= _DEAL_RISK_HIGH_WIN_PROBABILITY
        and idle_days > _DEAL_RISK_HIGH_IDLE_DAYS
    ):
        return "high", (
            f"Negócio de R$ {format_brl(expected_value)} com {win_probability}% de chance de "
            f"fechar, mas sem contato há {idle_days} dias."
        )

    if idle_days > _DEAL_RISK_MEDIUM_IDLE_DAYS or is_overdue:
        reason = "Tarefa atrasada — agende um contato." if is_overdue else (
            f"Sem atividade há {idle_days} dias."
        )
        return "medium", reason

    return "low", "Sob controle por enquanto."


def compute_action_type_and_urgency(lead: Lead, risk_level: str) -> tuple[str | None, str | None]:
    """AI Deal Coach's action recommendation — collapses risk_level (plus
    the lead's own status) into one concrete next action + urgency tag for
    the frontend's call-to-action button (LeadCard), distinct from
    next_best_action's full sentence. status is checked before risk_level:
    a lost lead always gets "drop_lead" regardless of risk (compute_deal_risk
    already returns "low" for it, so risk_level alone can't distinguish
    "lost" from "healthy"); a converted lead gets no action at all, same
    "nothing left to do" rule next_best_action already follows."""
    if lead.status == "lost":
        return "drop_lead", "low"
    if lead.status == "converted":
        return None, None
    if risk_level == "critical":
        return "call_now", "immediate"
    if risk_level == "high":
        return "send_message", "high"
    if risk_level == "medium":
        return "schedule_meeting", "medium"
    return "monitor", "low"


async def score_leads(db: AsyncSession, leads: list[Lead]) -> list[LeadResponse]:
    """Builds LeadResponse for each lead with score/score_breakdown
    overridden by compute_lead_score(), instead of the plain
    LeadResponse.model_validate(lead) every lead-returning endpoint used
    before this. Six extra queries total (recent automation activity,
    recent manual activity, compute_conversion_insights()'s own two,
    compute_response_metrics()'s own one, plus one for each lead's current
    lead_response_state) for the whole batch, regardless of how many leads
    are passed in — no N+1."""
    if not leads:
        return []

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=_RECENT_AUTOMATION_DAYS)
    lead_ids = [lead.id for lead in leads]

    # Every call site scopes `leads` to a single organization already (the
    # same invariant the automation/manual-activity queries below rely on
    # by filtering only on lead_id, not organization_id) — so the first
    # lead's organization_id is this whole batch's.
    organization_id = leads[0].organization_id
    insights = await compute_conversion_insights(db, organization_id)
    response_metrics = await compute_response_metrics(db, organization_id)

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

    # lead_response_state is a current-state snapshot, not a 30-day-windowed
    # rate like compute_response_metrics() above — so this queries all time,
    # picking each lead's most recent response-type entry (a later
    # "interested" supersedes an earlier plain "responded", etc.).
    response_state_stmt = select(
        LeadActivityLog.lead_id,
        LeadActivityLog.event_type,
        LeadActivityLog.duration_seconds,
        LeadActivityLog.created_at,
    ).where(
        LeadActivityLog.lead_id.in_(lead_ids),
        LeadActivityLog.event_type.in_(list(RESPONSE_STATE_BY_EVENT_TYPE)),
    )
    response_state_rows = (await db.execute(response_state_stmt)).all()
    latest_response_by_lead = {}
    for row in response_state_rows:
        current = latest_response_by_lead.get(row.lead_id)
        if current is None or row.created_at > current.created_at:
            latest_response_by_lead[row.lead_id] = row

    responses = []
    for lead in leads:
        latest_response = latest_response_by_lead.get(lead.id)
        lead_response_state = (
            RESPONSE_STATE_BY_EVENT_TYPE.get(latest_response.event_type, "no_response")
            if latest_response is not None
            else "no_response"
        )
        response_time_minutes = (
            round(latest_response.duration_seconds / 60)
            if latest_response is not None and latest_response.duration_seconds is not None
            else None
        )

        score, breakdown, win_probability = compute_lead_score(
            lead,
            has_recent_automation=lead.id in recent_lead_ids,
            has_recent_manual_activity=lead.id in recent_manual_activity_ids,
            task_completed_recently=lead.id in recent_task_completed_ids,
            insights=insights,
            lead_response_state=lead_response_state,
            best_response_industry=response_metrics.best_response_industry,
            now=now,
        )
        is_overdue = lead.next_action_due_at is not None and lead.next_action_due_at < now
        days_overdue = (now - lead.next_action_due_at).days if is_overdue else None
        days_idle = (now - lead.updated_at).days

        next_best_action = compute_next_best_action(
            lead, is_overdue=is_overdue, now=now, win_probability=win_probability
        )
        suggested_message = (
            generate_lead_message_by_action(lead, next_best_action, lead.owner_email or "the team")
            if next_best_action is not None and settings.AI_ENABLED
            else None
        )

        # Both always exact whole numbers: estimated_value is one of
        # 0/1000/5000/20000, win_probability an integer 0-100, so their
        # product divided by 100 never leaves a fraction — round() is just
        # a guard against float imprecision (e.g. 5000 * 42 / 100), not a
        # real rounding decision.
        estimated_value = get_lead_estimated_value(lead)
        expected_value = round(estimated_value * win_probability / 100)

        priority_reason = build_priority_reason(
            lead,
            estimated_value=round(estimated_value),
            win_probability=win_probability,
            days_idle=days_idle,
            is_overdue=is_overdue,
        )

        deal_risk_level, deal_risk_reason = compute_deal_risk(
            lead,
            expected_value=expected_value,
            win_probability=win_probability,
            is_overdue=is_overdue,
            now=now,
        )
        action_type, action_urgency = compute_action_type_and_urgency(lead, deal_risk_level)

        # Execution-assistance round — "ready to just do it" gate. Not its
        # own compute_*() function: it's a plain two-field AND already fully
        # expressed by values this loop iteration already has in scope, so a
        # separate function would just be indirection.
        is_ready_to_send = action_type == "send_message" and suggested_message is not None
        ready_to_send_message = suggested_message if is_ready_to_send else None

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
                    "win_probability": win_probability,
                    "estimated_value": round(estimated_value),
                    "expected_value": expected_value,
                    "priority_reason": priority_reason,
                    "deal_risk_level": deal_risk_level,
                    "deal_risk_reason": deal_risk_reason,
                    "next_best_action_type": action_type,
                    "next_best_action_urgency": action_urgency,
                    "ready_to_send_message": ready_to_send_message,
                    "auto_action_available": is_ready_to_send,
                    "lead_response_state": lead_response_state,
                    "response_time_minutes": response_time_minutes,
                }
            )
        )
    return responses


# Candidate-pool size for rank_leads_by_priority() — same value and rationale
# as GET /leads/priority's own docstring: comfortably above any realistic
# per-org lead count at this product stage.
_PRIORITY_CANDIDATE_POOL_SIZE = 200


async def rank_leads_by_priority(db: AsyncSession, organization_id: str) -> list[LeadResponse]:
    """Same urgency bucketing as GET /leads/priority (overdue tasks first,
    then due today, then future-dated, then no next_action at all),
    factored out so the workday command-mode engine
    (get_next_actionable_lead(), workday_engine.py) can reuse it without a
    second, separately-maintained copy of the bucket logic. Deliberately
    duplicates GET /leads/priority's own inline implementation rather than
    having that endpoint call this — it's already shipped and working, and
    this round's mandate is zero regression on existing routes.

    Within each urgency bucket, ordering is money-first (revenue-
    intelligence round): expected_value DESC, then win_probability DESC,
    then the base score DESC as a final tiebreaker — "money × probability ×
    urgency" instead of urgency-then-score alone."""
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

    scored.sort(
        key=lambda response: (
            bucket(response),
            -response.expected_value,
            -response.win_probability,
            -response.score,
        )
    )
    return scored
