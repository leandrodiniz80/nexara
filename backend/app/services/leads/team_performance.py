from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.leads.lead import Lead
from app.models.leads.lead_activity_log import LeadActivityLog
from app.models.notifications.user_notification import UserNotification
from app.schemas.leads.lead import LeadResponse
from app.schemas.performance import UserPerformanceResponse
from app.services.leads.enrichment import HIGH_VALUE_LEAD_THRESHOLD
from app.services.leads.execution_engine import ACTION_EFFECTIVENESS_EVENT_TYPE_BY_ACTION
from app.services.leads.scoring import RESPONSE_STATE_BY_EVENT_TYPE, score_leads

# Multi-user revenue-war round — the "team pool" cap, same rationale as
# GET /revenue/summary's own _REVENUE_POOL_SIZE: this needs every status
# (including "converted", which rank_leads_by_priority()'s own candidate
# pool always excludes), so a fresh, org-wide query is unavoidable here.
_TEAM_PERFORMANCE_POOL_SIZE = 2000

# compute_user_performance()'s own streak window — same 60-day lookback
# GET /workday/target's own per-user streak already uses
# (_STREAK_LOOKBACK_DAYS, workday.py), kept as its own literal here rather
# than importing that router-private constant.
_STREAK_LOOKBACK_DAYS = 60

# Auto-executed actions' own event types (auto_execute_engine(),
# execution_engine.py) — counted alongside the manual
# ACTION_EFFECTIVENESS_EVENT_TYPE_BY_ACTION markers below for
# actions_executed_today, since both are real "an action ran for this
# user" signals.
_AUTO_ACTION_EVENT_TYPES = ["action_auto_message", "action_auto_meeting"]
_ACTION_EVENT_TYPES = list(ACTION_EFFECTIVENESS_EVENT_TYPE_BY_ACTION.values()) + _AUTO_ACTION_EVENT_TYPES

# Gamification round's own badge bars (Task 4) — the prompt's own numbers.
_BADGE_CLOSER_REVENUE_THRESHOLD = 50000
_BADGE_SPEED_HUNTER_MINUTES = 10
_BADGE_HOT_PIPELINE_AT_RISK_THRESHOLD = 20000

# commission_estimate's own rate (Task 3) — the prompt's own number.
_COMMISSION_RATE = 0.05

# maybe_notify_underperformance()'s own dedup window (Task 5) — the
# prompt's own number, distinct from every other maybe_notify_* function
# in this codebase (all 6h) since this round's own spec asks for 12h.
_UNDERPERFORMANCE_ALERT_DEDUP_HOURS = 12
UNDERPERFORMANCE_ALERT_MARKER = "abaixo da média do time"


def _consecutive_days_streak(dates: set[date], today: date) -> int:
    """Same algorithm as GET /workday/target's own per-user streak
    (_current_streak(), workday.py) — kept as its own small copy here
    rather than importing that router-private function, same "small
    duplicated helper" precedent format_brl's own two independent copies
    already established. If today has no entry yet, counts from yesterday
    instead, so the streak doesn't drop to zero the moment the clock rolls
    over."""
    start = today if today in dates else today - timedelta(days=1)
    streak = 0
    day = start
    while day in dates:
        streak += 1
        day -= timedelta(days=1)
    return streak


async def score_org_leads(db: AsyncSession, organization_id: str) -> list[LeadResponse]:
    """Shared by compute_user_performance() and reassign_leads_if_needed()'s
    own caller (Adaptive Intelligence round, Task 4) — the org's full lead
    pool (every status, capped at _TEAM_PERFORMANCE_POOL_SIZE), scored
    once. Factored out of compute_user_performance()'s own original body
    unchanged (same query, same cap) so a caller that needs this same
    already-scored batch for something else (reassignment) doesn't force a
    second, redundant score_leads() pass in the same request — see
    compute_user_performance()'s own `leads` parameter."""
    leads_stmt = (
        select(Lead)
        .where(Lead.organization_id == organization_id, Lead.deleted_at.is_(None))
        .limit(_TEAM_PERFORMANCE_POOL_SIZE)
    )
    leads = (await db.execute(leads_stmt)).scalars().all()
    if not leads:
        return []
    return await score_leads(db, leads)


async def compute_user_performance(
    db: AsyncSession, organization_id: str, *, leads: list[LeadResponse] | None = None
) -> list[UserPerformanceResponse]:
    """Multi-user revenue-war round (Task 1) — one UserPerformanceResponse
    per distinct Lead.owner_email in this org (anyone with zero leads
    owned isn't a combatant in this leaderboard — see that schema's own
    docstring). Reuses score_leads() over the org's full lead pool (every
    status, capped at _TEAM_PERFORMANCE_POOL_SIZE) for revenue_converted/
    revenue_at_risk/pipeline_value, plus four LeadActivityLog aggregates
    (response-rate/response-time, actions-executed-today, streak, won-at
    dates for revenue_today/revenue_this_week — Elite round, Task 5)
    grouped by user_email in Python — six queries total regardless of team
    size, none per-user.

    `leads` (Adaptive Intelligence round, Task 4) lets a caller that
    already has this same org's own already-scored lead pool (GET
    /performance/leaderboard, which also needs it for
    reassign_leads_if_needed()) pass it straight in instead of this
    function fetching + scoring it a second time. None (every existing
    caller's own default, unchanged behavior) means "fetch and score it
    here, exactly like before this parameter existed."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    streak_window_start = now - timedelta(days=_STREAK_LOOKBACK_DAYS)

    scored = leads if leads is not None else await score_org_leads(db, organization_id)
    if not scored:
        return []
    leads_by_owner: dict[str, list] = {}
    for response in scored:
        if response.owner_email is None:
            continue
        leads_by_owner.setdefault(response.owner_email, []).append(response)

    if not leads_by_owner:
        return []

    # Response-rate/response-time — attributed to whoever's user_email is
    # on the message_sent/response-type LeadActivityLog row itself (see
    # UserPerformanceResponse's own docstring for the disclosed
    # approximation this implies).
    response_rows_stmt = select(
        LeadActivityLog.user_email, LeadActivityLog.event_type, LeadActivityLog.duration_seconds
    ).where(
        LeadActivityLog.organization_id == organization_id,
        LeadActivityLog.event_type.in_(["message_sent", *RESPONSE_STATE_BY_EVENT_TYPE]),
        LeadActivityLog.user_email.isnot(None),
    )
    response_rows = (await db.execute(response_rows_stmt)).all()

    sent_by_user: dict[str, int] = {}
    responded_by_user: dict[str, int] = {}
    response_times_by_user: dict[str, list[float]] = {}
    for row in response_rows:
        if row.event_type == "message_sent":
            sent_by_user[row.user_email] = sent_by_user.get(row.user_email, 0) + 1
            continue
        responded_by_user[row.user_email] = responded_by_user.get(row.user_email, 0) + 1
        if row.duration_seconds is not None:
            response_times_by_user.setdefault(row.user_email, []).append(row.duration_seconds / 60)

    # actions_executed_today
    actions_today_stmt = (
        select(LeadActivityLog.user_email, func.count(LeadActivityLog.id))
        .where(
            LeadActivityLog.organization_id == organization_id,
            LeadActivityLog.event_type.in_(_ACTION_EVENT_TYPES),
            LeadActivityLog.user_email.isnot(None),
            LeadActivityLog.created_at >= today_start,
        )
        .group_by(LeadActivityLog.user_email)
    )
    actions_today_by_user = dict((await db.execute(actions_today_stmt)).all())

    # streak_days — distinct "lead_won" dates per user, last 60 days.
    streak_rows_stmt = (
        select(LeadActivityLog.user_email, func.date(LeadActivityLog.created_at))
        .distinct()
        .where(
            LeadActivityLog.organization_id == organization_id,
            LeadActivityLog.event_type == "lead_won",
            LeadActivityLog.user_email.isnot(None),
            LeadActivityLog.created_at >= streak_window_start,
        )
    )
    streak_rows = (await db.execute(streak_rows_stmt)).all()
    dates_by_user: dict[str, set] = {}
    for user_email, won_date in streak_rows:
        dates_by_user.setdefault(user_email, set()).add(won_date)

    # Revenue Per User real-time (Elite round, Task 5) — this lead's own
    # most recent "lead_won" timestamp, keyed by lead_id (not user_email,
    # unlike every other aggregate above) so it can be matched against each
    # owner's own `owned` responses below. Windowed to the last 7 days —
    # this week's own window already covers today's, so one query serves
    # both revenue_today and revenue_this_week.
    won_at_stmt = select(LeadActivityLog.lead_id, LeadActivityLog.created_at).where(
        LeadActivityLog.organization_id == organization_id,
        LeadActivityLog.event_type == "lead_won",
        LeadActivityLog.created_at >= week_start,
    )
    won_at_rows = (await db.execute(won_at_stmt)).all()
    won_at_by_lead: dict = {}
    for lead_id, won_created_at in won_at_rows:
        current = won_at_by_lead.get(lead_id)
        if current is None or won_created_at > current:
            won_at_by_lead[lead_id] = won_created_at

    today = now.date()
    results: list[UserPerformanceResponse] = []
    for owner_email in sorted(leads_by_owner):
        owned = leads_by_owner[owner_email]
        leads_handled = len(owned)
        deals_closed = sum(1 for response in owned if response.status == "converted")
        revenue_converted = sum(
            response.estimated_value for response in owned if response.status == "converted"
        )
        revenue_at_risk = sum(
            response.expected_value
            for response in owned
            if response.deal_risk_level in ("high", "critical")
        )
        revenue_today = sum(
            response.estimated_value
            for response in owned
            if response.status == "converted"
            and (won_at := won_at_by_lead.get(response.id)) is not None
            and won_at >= today_start
        )
        revenue_this_week = sum(
            response.estimated_value
            for response in owned
            if response.status == "converted" and response.id in won_at_by_lead
        )
        pipeline_value = sum(
            response.expected_value
            for response in owned
            if response.status not in ("converted", "lost")
        )

        sent = sent_by_user.get(owner_email, 0)
        responded = responded_by_user.get(owner_email, 0)
        response_rate = round(responded / sent * 100, 1) if sent else 0.0

        times = response_times_by_user.get(owner_email)
        avg_response_time_minutes = round(sum(times) / len(times), 1) if times else None

        streak_days = _consecutive_days_streak(dates_by_user.get(owner_email, set()), today)

        badges: list[str] = []
        if revenue_converted >= _BADGE_CLOSER_REVENUE_THRESHOLD:
            badges.append("Closer")
        if avg_response_time_minutes is not None and avg_response_time_minutes < _BADGE_SPEED_HUNTER_MINUTES:
            badges.append("Speed Hunter")
        if revenue_at_risk >= _BADGE_HOT_PIPELINE_AT_RISK_THRESHOLD:
            badges.append("Hot Pipeline")

        results.append(
            UserPerformanceResponse(
                user_id=owner_email,
                name=owner_email,
                leads_handled=leads_handled,
                deals_closed=deals_closed,
                revenue_converted=revenue_converted,
                revenue_at_risk=revenue_at_risk,
                revenue_today=revenue_today,
                revenue_this_week=revenue_this_week,
                pipeline_value=pipeline_value,
                response_rate=response_rate,
                avg_response_time_minutes=avg_response_time_minutes,
                actions_executed_today=actions_today_by_user.get(owner_email, 0),
                commission_estimate=round(revenue_converted * _COMMISSION_RATE, 2),
                streak_days=streak_days,
                badges=badges,
            )
        )
    return results


def rank_user_performance(performances: list[UserPerformanceResponse]) -> list[UserPerformanceResponse]:
    """Leaderboard Engine's own sort (Task 2) — revenue_converted DESC,
    then response_rate DESC, then avg_response_time_minutes ASC (nulls
    last: a user who's never responded doesn't get to look faster than
    everyone who has). Shared by GET /performance/leaderboard and
    .../team-summary (for top/worst performer) so the two endpoints can
    never disagree about who's #1."""
    return sorted(
        performances,
        key=lambda performance: (
            -performance.revenue_converted,
            -performance.response_rate,
            performance.avg_response_time_minutes is None,
            performance.avg_response_time_minutes or 0.0,
        ),
    )


async def maybe_notify_underperformance(
    db: AsyncSession,
    *,
    organization_id: str,
    performances: list[UserPerformanceResponse],
    now: datetime,
) -> int:
    """Pressure System (Task 5) — flags whichever team members are below
    the team's own average revenue_converted OR have a slower-than-average
    avg_response_time_minutes (only compared against users who actually
    have a response-time figure — see UserPerformanceResponse's own "None
    until there's real signal" rule). A no-op with fewer than two team
    members (there's no meaningful "team average" to fall below with
    just one, or zero, data points). Org-wide-per-user alert, deduped on
    (user_email, own message marker) within _UNDERPERFORMANCE_ALERT_DEDUP_HOURS
    — same "own marker" technique IGNORED_LEADS_ALERT_MARKER (workday_engine.py)
    already established for an org-wide alert with no lead_id to key on.
    Caller commits; returns how many notifications were actually staged."""
    if len(performances) < 2:
        return 0

    avg_revenue = sum(performance.revenue_converted for performance in performances) / len(performances)
    response_times = [
        performance.avg_response_time_minutes
        for performance in performances
        if performance.avg_response_time_minutes is not None
    ]
    avg_response_time = sum(response_times) / len(response_times) if response_times else None

    underperformers = [
        performance
        for performance in performances
        if performance.revenue_converted < avg_revenue
        or (
            avg_response_time is not None
            and performance.avg_response_time_minutes is not None
            and performance.avg_response_time_minutes > avg_response_time
        )
    ]
    if not underperformers:
        return 0

    cutoff = now - timedelta(hours=_UNDERPERFORMANCE_ALERT_DEDUP_HOURS)
    user_ids = [performance.user_id for performance in underperformers]
    already_notified_stmt = select(UserNotification.user_email).where(
        UserNotification.organization_id == organization_id,
        UserNotification.user_email.in_(user_ids),
        UserNotification.message.contains(UNDERPERFORMANCE_ALERT_MARKER),
        UserNotification.created_at >= cutoff,
    )
    already_notified = set((await db.execute(already_notified_stmt)).scalars().all())

    notified = 0
    for performance in underperformers:
        if performance.user_id in already_notified:
            continue
        db.add(
            UserNotification(
                organization_id=organization_id,
                user_email=performance.user_id,
                lead_id=None,
                message=f"Seu desempenho está {UNDERPERFORMANCE_ALERT_MARKER} hoje.",
            )
        )
        notified += 1
    return notified


# Lead Reassignment Engine's own event type (Task 4, Adaptive Intelligence
# round) — a new, additive LeadActivityLog vocabulary entry (event_type is
# a plain String(32) column, no migration needed), same "log it, don't
# invent a table" pattern every other engine in this codebase already
# follows.
LEAD_REASSIGNED_EVENT_TYPE = "lead_reassigned"


async def reassign_leads_if_needed(
    db: AsyncSession,
    *,
    organization_id: str,
    leads: list[LeadResponse],
    user_performance: list[UserPerformanceResponse],
) -> int:
    """Lead Reassignment Engine (Task 4, Adaptive Intelligence round) —
    moves an underperforming owner's own high-value (expected_value >=
    HIGH_VALUE_LEAD_THRESHOLD), still-open leads to the org's current top
    performer (rank_user_performance()'s own #1). "Underperforming" means
    response_rate below the team average OR zero revenue_this_week (Elite
    round's own 7-day figure — reused rather than a fresh query, matching
    the prompt's own "revenue_converted == 0 in 7 days" ask) — either is a
    real enough signal on its own, so this is an OR, not an AND. A no-op
    with fewer than two team members (no meaningful "team average"/"top
    performer" to reassign toward) or when the underperformer IS the top
    performer (nothing to move away from themselves).

    `leads` is expected to be the exact same already-scored batch
    `user_performance` was itself computed from (compute_user_performance()'s
    own `leads` parameter exists for this) — reassignment reads each
    candidate's owner_email/status/expected_value straight off it, no
    second score_leads() pass. Idempotent: a lead already reassigned to the
    top performer on a previous call simply won't match `owner_email in
    underperformer_emails` again (the top performer is never counted as an
    underperformer against themselves), so re-running this doesn't
    reassign it again or log a duplicate entry. Caller commits; returns
    how many leads were actually reassigned this call."""
    if len(user_performance) < 2:
        return 0

    ranked = rank_user_performance(user_performance)
    top_performer = ranked[0]
    avg_response_rate = sum(performance.response_rate for performance in user_performance) / len(
        user_performance
    )

    underperformer_emails = {
        performance.user_id
        for performance in user_performance
        if performance.user_id != top_performer.user_id
        and (performance.response_rate < avg_response_rate or performance.revenue_this_week == 0)
    }
    if not underperformer_emails:
        return 0

    candidate_lead_ids = [
        response.id
        for response in leads
        if response.owner_email in underperformer_emails
        and response.status not in ("converted", "lost")
        and response.expected_value >= HIGH_VALUE_LEAD_THRESHOLD
    ]
    if not candidate_lead_ids:
        return 0

    lead_rows_stmt = select(Lead).where(Lead.id.in_(candidate_lead_ids))
    lead_rows = (await db.execute(lead_rows_stmt)).scalars().all()

    reassigned = 0
    for lead_row in lead_rows:
        previous_owner = lead_row.owner_email
        lead_row.owner_email = top_performer.user_id
        db.add(
            LeadActivityLog(
                organization_id=organization_id,
                lead_id=lead_row.id,
                lead_name=lead_row.name,
                event_type=LEAD_REASSIGNED_EVENT_TYPE,
                message=(
                    f"Lead redistribuído automaticamente de {previous_owner or 'sem dono'} "
                    f"para {top_performer.user_id} (baixo desempenho)."
                ),
                user_email=top_performer.user_id,
            )
        )
        reassigned += 1
    return reassigned
