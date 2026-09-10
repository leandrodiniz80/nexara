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

# Continuous Reassignment Engine's own per-org cooldown (Task 2, final
# round) — the prompt's own ask ("run on EVERY score_leads() call") read
# as "continuous across the app," not "recompute full team performance on
# every single request": reassign_leads_if_needed()'s own inputs
# (user_performance) need compute_user_performance(), which is itself a
# fresh score_leads() pass over the whole org — calling that on literally
# every score_leads() invocation would mean every lead list, every
# priority queue, every workday summary each triggering ANOTHER full
# org-wide scoring pass just to check reassignment, an unbounded
# multiplication this codebase's own "batch + in-memory hybrid" and "keep
# performance scalable" rules explicitly rule out. This in-memory,
# per-organization cooldown (same "process-local, no DB" pattern as
# _REALTIME_WEIGHTS_CACHE, scoring.py) lets any caller ask
# reassignment_check_due() first and skip the whole expensive path when
# it's already been checked recently — "continuous" in the sense that
# many different pages can each trigger it rather than one gated admin
# screen, while staying bounded to one real evaluation per org per
# window.
_REASSIGNMENT_CHECK_COOLDOWN_MINUTES = 15
_last_reassignment_check: dict[str, datetime] = {}


def reassignment_check_due(organization_id: str, now: datetime) -> bool:
    """True at most once per _REASSIGNMENT_CHECK_COOLDOWN_MINUTES per org
    — see _REASSIGNMENT_CHECK_COOLDOWN_MINUTES's own comment. Marks the
    check as done for this window as a side effect of returning True (the
    caller is expected to actually run the check immediately after), so
    two callers racing within the same request don't both pay for it —
    process-local, so this is a best-effort throttle, not a distributed
    lock; a second worker process would have its own independent cooldown
    clock, which is an acceptable, disclosed limitation for a plain
    scalability guard rather than a correctness-critical one."""
    last_checked = _last_reassignment_check.get(organization_id)
    if last_checked is not None and (now - last_checked) < timedelta(
        minutes=_REASSIGNMENT_CHECK_COOLDOWN_MINUTES
    ):
        return False
    _last_reassignment_check[organization_id] = now
    return True


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


# Continuous Reassignment Engine (Task 2, final round) — the prompt's own
# two upgrades over the original batch-trigger version:
#   dynamic threshold — the bar an underperformer is measured against now
#     scales with whoever the CURRENT top performer actually is (their own
#     response_rate * this ratio), instead of a fixed team-average line
#     that doesn't move when the leader pulls further ahead.
#   progressive movement — at most this many leads move per underperformer
#     per call (their own highest-value ones first), not every qualifying
#     lead at once — a gradual correction, not a single disruptive dump on
#     the top performer's plate.
_REASSIGNMENT_LEADER_RATIO_THRESHOLD = 0.5
_REASSIGNMENT_MAX_PER_OWNER_PER_CALL = 1


async def reassign_leads_if_needed(
    db: AsyncSession,
    *,
    organization_id: str,
    leads: list[LeadResponse],
    user_performance: list[UserPerformanceResponse],
) -> int:
    """Lead Reassignment Engine (Task 4, Adaptive Intelligence round;
    upgraded to a continuous, progressive engine — Task 2, final round) —
    moves an underperforming owner's own high-value (expected_value >=
    HIGH_VALUE_LEAD_THRESHOLD), still-open leads to the org's current top
    performer (rank_user_performance()'s own #1), at most
    _REASSIGNMENT_MAX_PER_OWNER_PER_CALL per owner per call (their own
    highest-expected_value ones first) rather than every qualifying lead
    at once. "Underperforming" means response_rate below
    _REASSIGNMENT_LEADER_RATIO_THRESHOLD of the CURRENT top performer's own
    response_rate (a dynamic bar — it moves with whoever's leading right
    now, not a fixed team average) OR zero revenue_this_week (Elite
    round's own 7-day figure — reused rather than a fresh query, matching
    the prompt's own "revenue_converted == 0 in 7 days" ask) — either is a
    real enough signal on its own, so this is an OR, not an AND. A no-op
    with fewer than two team members (no meaningful "leader" to compare
    against or reassign toward) or when the underperformer IS the top
    performer (nothing to move away from themselves).

    Callers this round (GET /performance/leaderboard and GET /workday/
    summary, both gated behind reassignment_check_due()'s own per-org
    cooldown — see that function's own docstring for why "run on every
    score_leads() call" is deliberately NOT read as "run inside
    score_leads() itself") make this check continuous across the app
    rather than gated behind one specific admin page, while still bounded
    to at most one real DB-backed evaluation per org per cooldown window —
    "continuous," not "on every single request," which would recompute
    full team performance (its own score_leads() pass) far more often than
    any real reassignment decision could possibly need.

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
    leader_response_rate_bar = top_performer.response_rate * _REASSIGNMENT_LEADER_RATIO_THRESHOLD

    underperformer_emails = {
        performance.user_id
        for performance in user_performance
        if performance.user_id != top_performer.user_id
        and (
            (top_performer.response_rate > 0 and performance.response_rate < leader_response_rate_bar)
            or performance.revenue_this_week == 0
        )
    }
    if not underperformer_emails:
        return 0

    candidates_by_owner: dict[str, list[LeadResponse]] = {}
    for response in leads:
        if (
            response.owner_email in underperformer_emails
            and response.status not in ("converted", "lost")
            and response.expected_value >= HIGH_VALUE_LEAD_THRESHOLD
        ):
            candidates_by_owner.setdefault(response.owner_email, []).append(response)
    if not candidates_by_owner:
        return 0

    candidate_lead_ids: list = []
    for owner_responses in candidates_by_owner.values():
        owner_responses.sort(key=lambda response: -response.expected_value)
        candidate_lead_ids.extend(
            response.id for response in owner_responses[:_REASSIGNMENT_MAX_PER_OWNER_PER_CALL]
        )

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


# Sales Pressure Engine (Task 1, final round) — one behavioral-control
# state per team member, deterministic, worst-condition-first (same
# severity-ordering style compute_deal_risk() already established).
PressureState = str  # "leader" | "neutral" | "at_risk" | "underperforming"


def compute_user_pressure_state(
    performance: UserPerformanceResponse,
    *,
    rank: int,
    team_size: int,
    avg_revenue_converted: float,
    avg_response_time_minutes: float | None,
    avg_pipeline_value: float,
) -> PressureState:
    """Sales Pressure Engine (Task 1, final round) — "leader"/"neutral"/
    "at_risk"/"underperforming" from three signals compute_user_
    performance() already computes per member (revenue_converted,
    avg_response_time_minutes, pipeline_value), each compared against the
    team's own average — no ML, plain rule table:

      leader — rank == 1 (rank_user_performance()'s own #1).
      underperforming — revenue_converted == 0 AND response slower than
        the team average (or no response-time figure at all yet) AND
        pipeline_value also below the team average — genuinely nothing
        going for them right now: no closes, slow to respond, and no real
        pipeline building either. pipeline_value is what keeps this from
        firing on someone who simply hasn't closed YET but is building a
        strong pipeline — see the next rule.
      at_risk — below average on revenue_converted or response time, but
        NOT all three at once (a real pipeline offsets an otherwise-bad
        pair, or being merely below-average on one front isn't yet a real
        problem) — a warning, not a crisis.
      neutral — everyone else: at or above average on every front,
        without being the outright #1.

    Always "neutral" with fewer than two team members — no meaningful
    team average or "leader" to compare against with just one, or zero,
    data points."""
    if team_size < 2:
        return "neutral"
    if rank == 1:
        return "leader"

    is_slow_response = (
        avg_response_time_minutes is not None
        and (
            performance.avg_response_time_minutes is None
            or performance.avg_response_time_minutes > avg_response_time_minutes
        )
    )
    is_zero_revenue = performance.revenue_converted == 0
    is_low_pipeline = performance.pipeline_value < avg_pipeline_value

    if is_zero_revenue and is_slow_response and is_low_pipeline:
        return "underperforming"

    is_below_avg_revenue = performance.revenue_converted < avg_revenue_converted
    if is_below_avg_revenue or is_slow_response:
        return "at_risk"

    return "neutral"


# maybe_notify_user_pressure()'s own dedup window — same 12h as the
# Pressure System's own maybe_notify_underperformance() above (this is
# its evolution, not an unrelated feature, so it shares the same cadence).
_PRESSURE_ALERT_DEDUP_HOURS = 12
# Each state's own dedup marker AND the substring compute_user_pressure_
# state() output maps to for classification — plain "structured info via
# string matching," same technique LOSS_REASON_MARKER (scoring.py)
# already established, since UserNotification has no separate "kind"
# column of its own to key on.
_PRESSURE_ALERT_MARKER_BY_STATE = {
    "leader": "Você está liderando o time",
    "at_risk": "atenção: seu desempenho caiu abaixo da média",
    "underperforming": "seu desempenho está crítico",
}
# Includes "neutral" too (not just the three alertable states above) —
# GET /performance/pressure-state (final round) needs a real sentence for
# every state, including the un-alerted one, so the frontend's own
# pressure banner never has to invent copy maybe_notify_user_pressure()
# itself doesn't produce (that function only ever notifies non-"neutral"
# states, by design — see its own docstring).
PRESSURE_MESSAGE_BY_STATE = {
    "leader": f"🏆 {_PRESSURE_ALERT_MARKER_BY_STATE['leader']} — continue assim!",
    "at_risk": f"⚠️ Atenção: {_PRESSURE_ALERT_MARKER_BY_STATE['at_risk']}.",
    "underperforming": f"🚨 Alerta: {_PRESSURE_ALERT_MARKER_BY_STATE['underperforming']} — reaja agora.",
    "neutral": "Desempenho dentro da média do time.",
}


async def maybe_notify_user_pressure(
    db: AsyncSession,
    *,
    organization_id: str,
    performances: list[UserPerformanceResponse],
    now: datetime,
) -> int:
    """Sales Pressure Engine's own notification half (Task 1, final
    round) — runs compute_user_pressure_state() over every team member
    and stages one UserNotification per non-"neutral" state:
    underperforming gets a strong alert (🚨), leader gets dominance
    reinforcement (🏆), at_risk gets a plain warning (⚠️). Additive
    alongside (not a replacement for) maybe_notify_underperformance()
    above — that one's own binary "below average" alert and this one's
    richer 4-state classification measure overlapping but not identical
    signals, same "layers compound, they don't override" precedent this
    codebase's own scoring bonuses already establish. Same per-(user,
    marker) dedup shape as every other maybe_notify_* function in this
    codebase, within _PRESSURE_ALERT_DEDUP_HOURS. A no-op with fewer than
    two team members. Caller commits; returns how many notifications were
    actually staged."""
    if len(performances) < 2:
        return 0

    ranked = rank_user_performance(performances)
    avg_revenue = sum(performance.revenue_converted for performance in performances) / len(performances)
    response_times = [
        performance.avg_response_time_minutes
        for performance in performances
        if performance.avg_response_time_minutes is not None
    ]
    avg_response_time = sum(response_times) / len(response_times) if response_times else None
    avg_pipeline_value = sum(performance.pipeline_value for performance in performances) / len(
        performances
    )

    state_by_user: dict[str, PressureState] = {}
    for rank, performance in enumerate(ranked, start=1):
        state = compute_user_pressure_state(
            performance,
            rank=rank,
            team_size=len(performances),
            avg_revenue_converted=avg_revenue,
            avg_response_time_minutes=avg_response_time,
            avg_pipeline_value=avg_pipeline_value,
        )
        if state != "neutral":
            state_by_user[performance.user_id] = state

    if not state_by_user:
        return 0

    cutoff = now - timedelta(hours=_PRESSURE_ALERT_DEDUP_HOURS)
    already_notified_stmt = select(UserNotification.user_email, UserNotification.message).where(
        UserNotification.organization_id == organization_id,
        UserNotification.user_email.in_(list(state_by_user)),
        UserNotification.created_at >= cutoff,
    )
    already_notified_rows = (await db.execute(already_notified_stmt)).all()
    already_notified = {
        (user_email, state)
        for user_email, message in already_notified_rows
        for state, marker in _PRESSURE_ALERT_MARKER_BY_STATE.items()
        if marker in message
    }

    notified = 0
    for user_email, state in state_by_user.items():
        if (user_email, state) in already_notified:
            continue
        db.add(
            UserNotification(
                organization_id=organization_id,
                user_email=user_email,
                lead_id=None,
                message=PRESSURE_MESSAGE_BY_STATE[state],
            )
        )
        notified += 1
    return notified
