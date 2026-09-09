import time
from datetime import date, timedelta, timezone
from datetime import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_session
from app.api.dependencies.common import get_db, get_request_id
from app.api.responses.api_response import ApiResponse
from app.core.config import settings
from app.models.leads.lead import Lead
from app.models.leads.lead_activity_log import LeadActivityLog
from app.models.notifications.user_notification import UserNotification
from app.schemas.leads.lead import LeadResponse
from app.schemas.workday import (
    ActionQueueItem,
    EnforcementStateResponse,
    WorkdayCompleteAndNextRequest,
    WorkdayCompleteAndNextResponse,
    WorkdayNextResponse,
    WorkdayPerformanceResponse,
    WorkdaySummaryResponse,
    WorkdayTargetResponse,
)
from app.services.leads.enrichment import HIGH_VALUE_LEAD_THRESHOLD, get_lead_estimated_value
from app.services.leads.execution_engine import (
    AUTO_EXECUTED_NOTIFICATION_PREFIX,
    AUTO_EXECUTION_NOTIFICATION_PREFIX,
    auto_execute_engine,
)
from app.services.leads.scoring import (
    compute_response_metrics,
    compute_revenue_attribution,
    compute_revenue_summary,
    rank_leads_by_priority,
    score_leads,
    top_revenue_bucket,
)
from app.services.leads.workday_engine import (
    build_action_queue,
    complete_lead_task,
    detect_user_failure_state,
    format_brl,
    generate_accountability_message,
    get_next_actionable_lead,
    get_next_mandatory_lead,
    maybe_notify_critical_deals,
    maybe_notify_focus_shift,
    maybe_notify_high_revenue_opportunity,
    maybe_notify_high_value_leads,
    maybe_notify_ignored_leads,
    maybe_notify_performance_alert,
    maybe_notify_pipeline_risk,
)

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/workday", tags=["Workday"])

# GET /workday/summary's leads_at_risk criteria — same "contacted, no recent
# touch" definition and default window as GET /leads/attention.
_AT_RISK_STALE_AFTER_DAYS = 3
# Sanity cap on the at-risk-leads row fetch (needed for per-lead
# enrichment_data, not just a count) — same rationale as the 200-row
# priority candidate pool: comfortably above any realistic per-org count at
# this product stage.
_AT_RISK_POOL_SIZE = 500
# GET /workday/summary's "top N" for high_priority_leads.
_HIGH_PRIORITY_TOP_N = 5
# GET /workday/target's fixed default — no per-user/org customization yet.
_DEFAULT_DAILY_TARGET = 5
# GET /workday/target's revenue-based target (Autonomous-sales-OS round) —
# the window _compute_daily_target_revenue() averages over, same 7-day
# span this codebase's other "steady, not noisy" windows already use
# (compute_response_metrics's own _RESPONSE_METRICS_WINDOW_DAYS uses 30 for
# a rarer signal; a week is enough here since conversions are the much
# more frequent event being averaged).
_DAILY_TARGET_REVENUE_WINDOW_DAYS = 7
# Revenue Acceleration Mode's own trigger (Task 3, revenue-maximization
# round) — this endpoint's own precise `gap > 5000` check, computed
# directly from the accurate gap just above. Kept as its own local
# constant, same value as scoring.py's compute_acceleration_mode() own
# _ACCELERATION_MODE_GAP_THRESHOLD, rather than importing it — that one is
# a cheap approximation feeding a different consumer (score_leads()); see
# WorkdayTargetResponse's own docstring for why the two can't share one
# computation.
_ACCELERATION_MODE_GAP_THRESHOLD = 5000.0

# Below this computed score, a lead is "low enough" to qualify for the
# workday queue even with no next_action set — roughly the midpoint of the
# score badge's own bands (destructive <31, warning 31-70, success 71-100).
_LOW_SCORE_THRESHOLD = 50
# A lead someone just finished doesn't reappear for this long, even if its
# score alone would otherwise still qualify it.
_JUST_COMPLETED_COOLDOWN_HOURS = 1
_CANDIDATE_POOL_SIZE = 200
_STREAK_LOOKBACK_DAYS = 60


def _require_caller(session: dict) -> tuple[str, str]:
    organization_id = session.get("organization_id")
    if organization_id is None:
        raise HTTPException(status_code=403, detail="Your account isn't part of an organization")

    user_email = session.get("email")
    if user_email is None:
        raise HTTPException(status_code=403, detail="Your session has no email on record")

    return organization_id, user_email


def _current_streak(completion_dates: set[date], today: date) -> int:
    """Consecutive days (ending today) with at least one completed task.
    If today has none yet, counts from yesterday instead — the streak
    shouldn't drop to zero the moment the clock rolls over, only once a
    full day passes with nothing done."""
    start = today if today in completion_dates else today - timedelta(days=1)
    streak = 0
    day = start
    while day in completion_dates:
        streak += 1
        day -= timedelta(days=1)
    return streak


async def _workday_stats(db: AsyncSession, organization_id: str, user_email: str, now: dt) -> tuple[int, int]:
    """(tasks_completed_today, streak_days) for this user — the "you've
    resolved N leads today" / streak numbers the frontend shows. Both read
    from LeadActivityLog's task_completed entries, attributed via the
    user_email column workday mode added."""
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_count_stmt = select(func.count(LeadActivityLog.id)).where(
        LeadActivityLog.organization_id == organization_id,
        LeadActivityLog.user_email == user_email,
        LeadActivityLog.event_type == "task_completed",
        LeadActivityLog.created_at >= today_start,
    )
    tasks_completed_today = (await db.execute(today_count_stmt)).scalar_one()

    streak_window_start = now - timedelta(days=_STREAK_LOOKBACK_DAYS)
    dates_stmt = (
        select(func.date(LeadActivityLog.created_at))
        .distinct()
        .where(
            LeadActivityLog.organization_id == organization_id,
            LeadActivityLog.user_email == user_email,
            LeadActivityLog.event_type == "task_completed",
            LeadActivityLog.created_at >= streak_window_start,
        )
    )
    completion_dates = set((await db.execute(dates_stmt)).scalars().all())
    streak_days = _current_streak(completion_dates, now.date())

    return tasks_completed_today, streak_days


@router.get("/next", response_model=ApiResponse[WorkdayNextResponse])
async def get_workday_next(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[WorkdayNextResponse]:
    """The engine behind "Começar meu dia": always returns exactly one lead
    to work on right now, or none if the queue is empty.

    Anti-chaos lock: if the caller already has a lead in focus
    (in_focus=True, focused_by_email=them) and it's still unresolved
    (not converted, next_action still set), this is idempotent — it
    returns that same lead again rather than picking a new one, so calling
    it mid-session never lets someone skip ahead without finishing what
    they started. A stale focus (the lead got resolved through some other
    flow — status changed elsewhere, task completed elsewhere) is cleared
    automatically before picking fresh, so there's no permanent deadlock.

    Candidate pool: same worst-first ordering as GET /leads/priority
    (next_action_due_at ASC NULLS LAST, then computed score ASC), filtered
    to leads with either a pending next_action or a low score, excluding
    anything currently in focus for a *different* user and anything with a
    task_completed entry in the last hour (so a just-finished lead doesn't
    immediately resurface). Score can't be ordered in SQL (it's computed),
    so this fetches a generous pool via the one ordering SQL *can* express
    and re-sorts in Python — same approach as /leads/priority.
    """
    start = time.perf_counter()
    organization_id, user_email = _require_caller(session)
    now = dt.now(timezone.utc)

    current_focus_stmt = select(Lead).where(
        Lead.organization_id == organization_id,
        Lead.focused_by_email == user_email,
        Lead.in_focus.is_(True),
    )
    current_focus = (await db.execute(current_focus_stmt)).scalar_one_or_none()

    if current_focus is not None and current_focus.status != "converted" and current_focus.next_action is not None:
        (scored_current,) = await score_leads(db, [current_focus])
        tasks_completed_today, streak_days = await _workday_stats(db, organization_id, user_email, now)
        return ApiResponse(
            success=True,
            data=WorkdayNextResponse(
                lead=scored_current,
                is_new_focus=False,
                tasks_completed_today=tasks_completed_today,
                streak_days=streak_days,
            ),
            request_id=request_id,
            execution_time=time.perf_counter() - start,
        )

    if current_focus is not None:
        # Stale — resolved through some other flow. Clear before picking.
        current_focus.in_focus = False
        current_focus.focused_at = None
        current_focus.focused_by_email = None

    candidate_stmt = (
        select(Lead)
        .where(
            Lead.organization_id == organization_id,
            Lead.deleted_at.is_(None),
            Lead.status != "converted",
            or_(Lead.in_focus.is_(False), Lead.focused_by_email == user_email),
        )
        .order_by(Lead.next_action_due_at.asc().nulls_last())
        .limit(_CANDIDATE_POOL_SIZE)
    )
    candidates = (await db.execute(candidate_stmt)).scalars().all()
    candidates_by_id = {lead.id: lead for lead in candidates}

    cooldown_cutoff = now - timedelta(hours=_JUST_COMPLETED_COOLDOWN_HOURS)
    recently_completed_stmt = select(LeadActivityLog.lead_id).where(
        LeadActivityLog.organization_id == organization_id,
        LeadActivityLog.event_type == "task_completed",
        LeadActivityLog.created_at >= cooldown_cutoff,
    )
    recently_completed_ids = set((await db.execute(recently_completed_stmt)).scalars().all())

    scored = await score_leads(db, candidates)
    eligible = [
        response
        for response in scored
        if response.id not in recently_completed_ids
        and (response.next_action is not None or response.score < _LOW_SCORE_THRESHOLD)
    ]
    eligible.sort(
        key=lambda response: (
            response.next_action_due_at is None,
            response.next_action_due_at,
            response.score,
        )
    )

    if not eligible:
        await db.commit()
        tasks_completed_today, streak_days = await _workday_stats(db, organization_id, user_email, now)
        return ApiResponse(
            success=True,
            data=WorkdayNextResponse(
                lead=None,
                is_new_focus=False,
                tasks_completed_today=tasks_completed_today,
                streak_days=streak_days,
            ),
            request_id=request_id,
            execution_time=time.perf_counter() - start,
        )

    next_lead = candidates_by_id[eligible[0].id]
    next_lead.in_focus = True
    next_lead.focused_at = now
    next_lead.focused_by_email = user_email

    await db.commit()
    await db.refresh(next_lead)

    (scored_next,) = await score_leads(db, [next_lead])
    tasks_completed_today, streak_days = await _workday_stats(db, organization_id, user_email, now)

    return ApiResponse(
        success=True,
        data=WorkdayNextResponse(
            lead=scored_next,
            is_new_focus=True,
            tasks_completed_today=tasks_completed_today,
            streak_days=streak_days,
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


def _build_focus_message(
    *, overdue_tasks: int, today_tasks: int, leads_at_risk: int, revenue_at_risk: float
) -> str:
    """The Command Center's headline sentence — built here, not the
    frontend, same "backend writes the sentence" rule the timeline/activity
    feed already follow. Checked worst-first: overdue-with-money-at-stake
    is the strongest nudge, an empty day is the only case with no urgency
    to convey at all."""
    if overdue_tasks > 0 and revenue_at_risk > 0:
        return (
            f"Você tem {overdue_tasks} leads atrasados e pode perder até "
            f"R$ {format_brl(revenue_at_risk)} hoje se não agir."
        )
    if overdue_tasks > 0:
        return f"Você tem {overdue_tasks} leads atrasados esperando ação."
    if today_tasks > 0:
        return f"Você tem {today_tasks} ações para fazer hoje."
    if leads_at_risk > 0:
        return f"Você tem {leads_at_risk} leads esfriando sem contato recente."
    return "Nenhuma ação urgente agora — bom momento para prospectar novos leads."


async def _count_overdue_tasks(db: AsyncSession, organization_id: str, now: dt) -> int:
    """Shared by GET /workday/summary and GET /workday/performance — same
    query, same index (ix_leads_org_id_next_action_due_at)."""
    stmt = select(func.count(Lead.id)).where(
        Lead.organization_id == organization_id,
        Lead.deleted_at.is_(None),
        Lead.next_action_due_at.isnot(None),
        Lead.next_action_due_at < now,
    )
    return (await db.execute(stmt)).scalar_one()


def _compute_revenue_at_risk(ranked: list[LeadResponse], *, now: dt, stale_cutoff: dt) -> int:
    """"Money genuinely at risk, probability-adjusted" — contacted leads
    that are either overdue or stale (updated_at older than stale_cutoff),
    summed by expected_value (not the raw estimated_value
    estimated_revenue_at_risk/estimated_revenue_lost elsewhere use). Reuses
    whatever rank_leads_by_priority() already scored — zero extra query.
    Shared by GET /workday/summary and .../performance."""
    total = 0
    for response in ranked:
        if response.status != "contacted":
            continue
        is_overdue = (
            response.next_action_due_at is not None and response.next_action_due_at < now
        )
        is_stale = response.updated_at < stale_cutoff
        if is_overdue or is_stale:
            total += response.expected_value
    return total


def _sum_today_potential_revenue(ranked: list[LeadResponse], *, now: dt) -> int:
    """The Command Center's "Hoje você pode gerar R$ X" — expected_value
    summed over today's actionable leads (overdue or due today). Reuses the
    same already-scored ranked list _compute_revenue_at_risk does."""
    total = 0
    for response in ranked:
        due = response.next_action_due_at
        if due is None:
            continue
        if response.is_overdue or due.date() == now.date():
            total += response.expected_value
    return total


def _compute_deal_risk_summary(ranked: list[LeadResponse]) -> tuple[int, int]:
    """(money_at_risk_today, critical_deals_count) — AI Deal Coach round.
    Reuses whatever rank_leads_by_priority() already scored (deal_risk_level
    is populated by score_leads() for every response in `ranked`), zero
    extra query. Shared by GET /workday/summary and .../performance, same
    "reuse the already-scored list" pattern as _compute_revenue_at_risk."""
    critical = [response for response in ranked if response.deal_risk_level == "critical"]
    money_at_risk = sum(response.expected_value for response in critical)
    return money_at_risk, len(critical)


async def _compute_money_saved_today(db: AsyncSession, organization_id: str, today_start: dt) -> float:
    """A proxy, not an exact figure (AI Deal Coach round): the deal_risk_level
    a now-completed lead had *before* its task was finished isn't recoverable
    at read time (completing it clears next_action_due_at and bumps
    updated_at, so recomputing risk now would show "low" regardless of what
    it was) — so this sums estimated_value for leads with a task_completed
    activity today whose estimated_value clears HIGH_VALUE_LEAD_THRESHOLD,
    as a stand-in for "high-value deals that got acted on today instead of
    going cold." Two queries: distinct lead_ids from today's completions,
    then those leads' rows for their enrichment_data."""
    completed_ids_stmt = (
        select(LeadActivityLog.lead_id)
        .distinct()
        .where(
            LeadActivityLog.organization_id == organization_id,
            LeadActivityLog.event_type == "task_completed",
            LeadActivityLog.created_at >= today_start,
        )
    )
    completed_ids = (await db.execute(completed_ids_stmt)).scalars().all()
    if not completed_ids:
        return 0.0

    completed_leads_stmt = select(Lead).where(Lead.id.in_(completed_ids))
    completed_leads = (await db.execute(completed_leads_stmt)).scalars().all()

    return sum(
        value
        for lead in completed_leads
        if (value := get_lead_estimated_value(lead)) >= HIGH_VALUE_LEAD_THRESHOLD
    )


async def _compute_daily_target_revenue(db: AsyncSession, organization_id: str, cutoff: dt) -> float:
    """GET /workday/target's revenue-based target (Autonomous-sales-OS
    round) — average converted revenue per day over the last
    _DAILY_TARGET_REVENUE_WINDOW_DAYS: sums estimated_value for every lead
    with a "lead_won" LeadActivityLog entry (the same precise conversion-
    moment marker compute_revenue_summary()'s own revenue_generated_today
    reads, scoring.py) since `cutoff`, divided by the window length. 0.0
    with no conversions in the window — a real "nothing to average yet"
    answer, not a misleading default. Two queries: distinct lead_won
    lead_ids in the window, then those leads' rows for enrichment_data."""
    won_ids_stmt = (
        select(LeadActivityLog.lead_id)
        .distinct()
        .where(
            LeadActivityLog.organization_id == organization_id,
            LeadActivityLog.event_type == "lead_won",
            LeadActivityLog.created_at >= cutoff,
        )
    )
    won_ids = (await db.execute(won_ids_stmt)).scalars().all()
    if not won_ids:
        return 0.0

    won_leads_stmt = select(Lead).where(Lead.id.in_(won_ids))
    won_leads = (await db.execute(won_leads_stmt)).scalars().all()
    total = sum(get_lead_estimated_value(lead) for lead in won_leads)
    return total / _DAILY_TARGET_REVENUE_WINDOW_DAYS


async def _count_auto_actions_today(db: AsyncSession, organization_id: str, today_start: dt) -> int:
    """Execution-assistance round, widened by the Autonomous-sales-OS
    round's auto_execute_engine(). Counts UserNotification rows matching
    either that engine's own AUTO_EXECUTED_NOTIFICATION_PREFIX or the
    original AUTO_EXECUTION_NOTIFICATION_PREFIX it replaced (kept only so
    historical rows written before this round still count — see that
    constant's own updated docstring, execution_engine.py) created today —
    deliberately not LeadActivityLog's "message_sent" entries, which also
    include manual "Enviar agora" clicks this field excludes on purpose."""
    stmt = select(func.count(UserNotification.id)).where(
        UserNotification.organization_id == organization_id,
        or_(
            UserNotification.message.startswith(AUTO_EXECUTED_NOTIFICATION_PREFIX),
            UserNotification.message.startswith(AUTO_EXECUTION_NOTIFICATION_PREFIX),
        ),
        UserNotification.created_at >= today_start,
    )
    return (await db.execute(stmt)).scalar_one()


_RESPONSE_TYPE_EVENT_TYPES = ["lead_responded", "lead_interested", "lead_rejected"]
# _compute_response_metrics_today()'s "fast" bar — same <30min cutoff
# compute_lead_score()'s own "Fast response from lead" bonus uses
# (_FAST_RESPONSE_MINUTES, scoring.py).
_FAST_RESPONSE_MINUTES_TODAY = 30


async def _compute_response_metrics_today(
    db: AsyncSession, organization_id: str, today_start: dt
) -> tuple[float, int, float | None, int]:
    """(response_rate_today, responses_received_today, avg_response_time_today,
    fast_responses_today) — feedback-loop-of-outcomes round's first two,
    sales-operating-system round's last two. Today-only counterpart to
    compute_response_metrics()'s steadier 30-day figure (scoring.py): same
    message_sent vs. response-type event_type split, just scoped to today
    and without the industry breakdown that endpoint's best_response_industry
    needs. One query — raw rows (not grouped counts), since
    avg_response_time_today/fast_responses_today need each row's own
    duration_seconds, not just a count per event_type."""
    stmt = select(LeadActivityLog.event_type, LeadActivityLog.duration_seconds).where(
        LeadActivityLog.organization_id == organization_id,
        LeadActivityLog.event_type.in_(["message_sent", *_RESPONSE_TYPE_EVENT_TYPES]),
        LeadActivityLog.created_at >= today_start,
    )
    rows = (await db.execute(stmt)).all()

    sent_today = sum(1 for row in rows if row.event_type == "message_sent")
    response_rows = [row for row in rows if row.event_type in _RESPONSE_TYPE_EVENT_TYPES]
    responses_received_today = len(response_rows)
    response_rate_today = (
        round(responses_received_today / sent_today * 100, 1) if sent_today else 0.0
    )

    response_times_today = [
        row.duration_seconds / 60 for row in response_rows if row.duration_seconds is not None
    ]
    avg_response_time_today = (
        round(sum(response_times_today) / len(response_times_today), 1)
        if response_times_today
        else None
    )
    fast_responses_today = sum(
        1 for minutes in response_times_today if minutes < _FAST_RESPONSE_MINUTES_TODAY
    )

    return response_rate_today, responses_received_today, avg_response_time_today, fast_responses_today


def _compute_response_and_pipeline_pressure(
    ranked: list[LeadResponse],
) -> tuple[int, int, int, int]:
    """(pending_responses_count, ignored_count, high_value_at_risk_count,
    pipeline_expected_value) — sales-operating-system round. All four reuse
    whatever rank_leads_by_priority() already scored
    (has_pending_response/response_delay_minutes/deal_risk_level/
    expected_value, all populated by score_leads()), zero extra query.
    pending_responses_count is every lead with a message out and no reply
    yet, regardless of how long (WorkdaySummaryResponse's own field);
    ignored_count narrows that to specifically >24h
    (_PENDING_RESPONSE_DELAY_MINUTES_HIGH, scoring.py) — maybe_notify_ignored_leads()'s
    own trigger, not exposed in the response schema (only asked for the
    broader count there). pipeline_expected_value is scoped to "open" leads
    (new/contacted) — rank_leads_by_priority's own candidate pool also
    includes "lost" leads (it only ever excludes "converted"), but a lost
    lead's expected_value is always 0 anyway (compute_win_probability
    short-circuits win_probability to 0 for "lost", scoring.py), so this
    filter is about being literal ("all open leads"), not about changing
    the sum."""
    pending_responses_count = sum(1 for response in ranked if response.has_pending_response)
    ignored_count = sum(
        1
        for response in ranked
        if response.has_pending_response
        and response.response_delay_minutes is not None
        and response.response_delay_minutes > 24 * 60
    )
    high_value_at_risk_count = sum(
        1
        for response in ranked
        if response.expected_value >= HIGH_VALUE_LEAD_THRESHOLD
        and response.deal_risk_level in ("high", "critical")
    )
    pipeline_expected_value = sum(
        response.expected_value for response in ranked if response.status in ("new", "contacted")
    )
    return pending_responses_count, ignored_count, high_value_at_risk_count, pipeline_expected_value


def _compute_lost_opportunity_today(ranked: list[LeadResponse]) -> int:
    """"Oportunidade perdida hoje" (Task 6, revenue-maximization round) —
    sum of opportunity_cost (Task 1, scoring.py) across leads not touched
    today (days_since_last_activity >= 1): leads sitting idle right now,
    weighted by how much revenue upside each one represents versus the
    org's single highest-value lead. Reuses whatever rank_leads_by_priority()
    already scored, zero extra query."""
    return sum(
        response.opportunity_cost
        for response in ranked
        if response.days_since_last_activity >= 1 and response.status not in ("converted", "lost")
    )


@router.get("/summary", response_model=ApiResponse[WorkdaySummaryResponse])
async def get_workday_summary(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[WorkdaySummaryResponse]:
    """The Command Center's "what does today look like" snapshot: how many
    tasks are due/overdue, how many leads are going cold, and a rough
    R$-at-risk estimate — collapsed into one focus_message so the dashboard
    has a single headline to lead with instead of four separate numbers.

    Nine queries total, none per-row (up to 7 more, conditional: one dedup
    check each for maybe_notify_high_value_leads()/maybe_notify_critical_deals()/
    maybe_notify_ignored_leads()/maybe_notify_pipeline_risk()/
    maybe_notify_high_revenue_opportunity()/maybe_notify_focus_shift()
    (revenue-maximization round), one Lead row-fetch for
    auto_execute_engine() (execution_engine.py) — all seven only when
    there's an actual candidate/threshold breach, and the last only when
    settings.AUTO_MODE_ENABLED is even on, which it isn't by default):
    pending_responses_count/high_value_at_risk_count/pipeline_expected_value
    (_compute_response_and_pipeline_pressure) also reuse `ranked`, zero
    extra query.
    today/overdue are plain COUNTs (backed by ix_leads_org_id_next_action_due_at,
    same index GET /leads/tasks uses); leads-at-risk is the same WHERE shape
    as GET /leads/attention (ix_leads_org_id_status_updated_at), fetched as
    rows (not just a count) since estimated_revenue_at_risk needs each
    one's enrichment_data; high_priority_leads/revenue_at_risk/
    today_potential_revenue/money_at_risk_today/critical_deals_count all
    reuse the one rank_leads_by_priority() call (candidate query +
    score_leads' own one extra query) — the same cost GET /leads/priority
    already pays elsewhere on this same dashboard; the 7th, unconditional,
    is auto_actions_executed_today's own count (_count_auto_actions_today);
    the 8th and 9th are compute_revenue_attribution()'s own two-query pass
    (Revenue-loop round) for top_revenue_action/top_revenue_industry/
    top_revenue_company_size."""
    start = time.perf_counter()
    organization_id, user_email = _require_caller(session)
    now = dt.now(timezone.utc)

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    today_tasks_stmt = select(func.count(Lead.id)).where(
        Lead.organization_id == organization_id,
        Lead.deleted_at.is_(None),
        Lead.next_action_due_at.isnot(None),
        Lead.next_action_due_at >= today_start,
        Lead.next_action_due_at < today_end,
    )
    today_tasks = (await db.execute(today_tasks_stmt)).scalar_one()

    overdue_tasks = await _count_overdue_tasks(db, organization_id, now)

    at_risk_cutoff = now - timedelta(days=_AT_RISK_STALE_AFTER_DAYS)
    at_risk_stmt = (
        select(Lead)
        .where(
            Lead.organization_id == organization_id,
            Lead.deleted_at.is_(None),
            Lead.status == "contacted",
            Lead.updated_at < at_risk_cutoff,
        )
        .limit(_AT_RISK_POOL_SIZE)
    )
    at_risk_leads = (await db.execute(at_risk_stmt)).scalars().all()
    leads_at_risk = len(at_risk_leads)
    estimated_revenue_at_risk = sum(get_lead_estimated_value(lead) for lead in at_risk_leads)

    ranked = await rank_leads_by_priority(db, organization_id)
    high_priority_leads = len(ranked[:_HIGH_PRIORITY_TOP_N])
    revenue_at_risk = _compute_revenue_at_risk(ranked, now=now, stale_cutoff=at_risk_cutoff)
    today_potential_revenue = _sum_today_potential_revenue(ranked, now=now)
    money_at_risk_today, critical_deals_count = _compute_deal_risk_summary(ranked)
    pending_responses_count, ignored_count, high_value_at_risk_count, pipeline_expected_value = (
        _compute_response_and_pipeline_pressure(ranked)
    )

    focus_message = _build_focus_message(
        overdue_tasks=overdue_tasks,
        today_tasks=today_tasks,
        leads_at_risk=leads_at_risk,
        revenue_at_risk=estimated_revenue_at_risk,
    )

    # Revenue-intelligence round: a high-value lead going cold gets its own
    # per-lead alert (distinct from the org-wide "failing" one GET
    # /workday/performance already sends) — reuses `ranked`, no new query.
    notified_count = await maybe_notify_high_value_leads(
        db, organization_id=organization_id, leads=ranked, now=now
    )
    # AI Deal Coach round — separate per-lead alert for critical-risk deals,
    # reusing the same `ranked` list (see maybe_notify_critical_deals's own
    # docstring for how its dedup window relates to the high-value alert's).
    notified_count += await maybe_notify_critical_deals(
        db, organization_id=organization_id, leads=ranked, now=now
    )
    # Autonomous-sales-OS round — a no-op while settings.AUTO_MODE_ENABLED
    # is off (the default); see auto_execute_engine()'s own docstring
    # (execution_engine.py) for its two auto-execution rules and daily cap
    # (its own schedule_meeting overdue-grace relaxation reads
    # response.acceleration_mode straight off each already-scored `ranked`
    # entry, no extra parameter needed here).
    auto_executed_count = await auto_execute_engine(db, organization_id, ranked)
    # Sales-operating-system round — two more org-wide nudges, both no-ops
    # most of the time (gated behind their own thresholds) and both reusing
    # data already computed above (pending_responses_count, revenue_at_risk)
    # — zero new queries beyond their own dedup checks.
    notified_count += await maybe_notify_ignored_leads(
        db,
        organization_id=organization_id,
        user_email=user_email,
        ignored_count=ignored_count,
        now=now,
    )
    notified_count += await maybe_notify_pipeline_risk(
        db,
        organization_id=organization_id,
        user_email=user_email,
        revenue_at_risk=revenue_at_risk,
        now=now,
    )
    # Revenue-loop round — proactive "close this one" nudge for a big,
    # likely-to-close deal, reusing the same `ranked` list.
    notified_count += await maybe_notify_high_revenue_opportunity(
        db, organization_id=organization_id, leads=ranked, now=now
    )
    # Revenue-maximization round (Task 5) — redirects attention away from
    # low-value leads when a much bigger one sits neglected, reusing the
    # same `ranked` list.
    notified_count += await maybe_notify_focus_shift(
        db, organization_id=organization_id, user_email=user_email, leads=ranked, now=now
    )
    if notified_count or auto_executed_count:
        await db.commit()

    auto_actions_executed_today = await _count_auto_actions_today(db, organization_id, today_start)
    response_metrics = await compute_response_metrics(db, organization_id)

    # Execution-engine round — Task 2's own "next_mandatory_lead_id", reusing
    # this same `ranked` list, zero extra query.
    action_queue = build_action_queue(ranked)
    mandatory_lead = get_next_mandatory_lead(action_queue)

    # Revenue-loop round — the Command Center's "O que mais gera dinheiro
    # hoje" — reduces compute_revenue_attribution()'s own three breakdowns
    # down to one winner each.
    revenue_attribution = await compute_revenue_attribution(db, organization_id)
    top_revenue_action = top_revenue_bucket(revenue_attribution.revenue_by_action)
    top_revenue_industry = top_revenue_bucket(revenue_attribution.revenue_by_industry)
    top_revenue_company_size = top_revenue_bucket(revenue_attribution.revenue_by_company_size)

    # Revenue-maximization round (Task 6) — "Oportunidade perdida hoje"
    # and "Top padrão de receita", both additive/derived at zero extra
    # query cost from data already computed above.
    lost_opportunity_today = _compute_lost_opportunity_today(ranked)
    top_revenue_combination = revenue_attribution.top_combination

    return ApiResponse(
        success=True,
        data=WorkdaySummaryResponse(
            today_tasks=today_tasks,
            overdue_tasks=overdue_tasks,
            high_priority_leads=high_priority_leads,
            leads_at_risk=leads_at_risk,
            estimated_revenue_at_risk=estimated_revenue_at_risk,
            focus_message=focus_message,
            revenue_at_risk=revenue_at_risk,
            today_potential_revenue=today_potential_revenue,
            money_in_play_today=today_potential_revenue,
            money_at_risk_today=money_at_risk_today,
            critical_deals_count=critical_deals_count,
            auto_actions_executed_today=auto_actions_executed_today,
            response_rate=response_metrics.response_rate,
            pending_responses_count=pending_responses_count,
            high_value_at_risk_count=high_value_at_risk_count,
            pipeline_expected_value=pipeline_expected_value,
            next_mandatory_lead_id=mandatory_lead.id if mandatory_lead is not None else None,
            top_revenue_action=top_revenue_action,
            top_revenue_industry=top_revenue_industry,
            top_revenue_company_size=top_revenue_company_size,
            lost_opportunity_today=lost_opportunity_today,
            top_revenue_combination=top_revenue_combination,
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/enforcement-state", response_model=ApiResponse[EnforcementStateResponse])
async def get_workday_enforcement_state(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[EnforcementStateResponse]:
    """Autonomous-sales-OS round's hard-enforcement gate: reuses the exact
    same rank_leads_by_priority() -> build_action_queue() ->
    get_next_mandatory_lead() pipeline GET /workday/summary's own
    next_mandatory_lead_id already computes, exposed here as its own
    endpoint with enough lead detail (name/company/phone/expected_value)
    for the frontend to render a fullscreen blocking overlay without a
    second fetch, plus a human reason and a guaranteed-executable
    required_action (see EnforcementStateResponse's own docstring for the
    "monitor" fallback). A fresh rank_leads_by_priority() call — same one
    query cost GET /workday/action-queue already pays independently."""
    start = time.perf_counter()
    organization_id, _user_email = _require_caller(session)

    ranked = await rank_leads_by_priority(db, organization_id)
    queue = build_action_queue(ranked)
    mandatory_lead = get_next_mandatory_lead(queue)

    if mandatory_lead is None:
        return ApiResponse(
            success=True,
            data=EnforcementStateResponse(blocked=False),
            request_id=request_id,
            execution_time=time.perf_counter() - start,
        )

    # Mirrors get_next_mandatory_lead()'s own OR condition, checked in the
    # same order (critical first) so the reason always names whichever
    # condition actually applied.
    if mandatory_lead.deal_risk_level == "critical":
        reason = "Você tem um lead crítico que precisa de ação imediata"
    elif mandatory_lead.response_delay_minutes is not None and mandatory_lead.response_delay_minutes > 60:
        reason = "Um lead está aguardando resposta há mais de 60 minutos"
    else:
        reason = "Ação necessária agora"

    required_action = mandatory_lead.next_best_action_type
    if required_action not in ("send_message", "call_now", "schedule_meeting"):
        required_action = "send_message"

    return ApiResponse(
        success=True,
        data=EnforcementStateResponse(
            blocked=True,
            lead_id=mandatory_lead.id,
            name=mandatory_lead.name,
            company_name=mandatory_lead.company_name,
            phone=mandatory_lead.phone,
            expected_value=mandatory_lead.expected_value,
            required_action=required_action,
            next_best_action=mandatory_lead.next_best_action,
            reason=reason,
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/action-queue", response_model=ApiResponse[list[ActionQueueItem]])
async def get_action_queue(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[ActionQueueItem]]:
    """Execution-engine round — Task 1's "Fila de execução": the top 10
    leads worth acting on right now, risk-first then money-first
    (build_action_queue(), workday_engine.py), built from a fresh
    rank_leads_by_priority() call — same one query cost GET /leads/priority
    and /workday/summary each already pay independently."""
    start = time.perf_counter()
    organization_id, _user_email = _require_caller(session)

    ranked = await rank_leads_by_priority(db, organization_id)
    queue = build_action_queue(ranked)

    return ApiResponse(
        success=True,
        data=[
            ActionQueueItem(
                lead_id=lead.id,
                name=lead.name,
                deal_risk_level=lead.deal_risk_level,
                expected_value=lead.expected_value,
                next_best_action=lead.next_best_action,
                next_best_action_type=lead.next_best_action_type,
                next_best_action_urgency=lead.next_best_action_urgency,
            )
            for lead in queue
        ],
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.post("/complete-and-next", response_model=ApiResponse[WorkdayCompleteAndNextResponse])
async def complete_and_next(
    body: WorkdayCompleteAndNextRequest,
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[WorkdayCompleteAndNextResponse]:
    """The Command Center's continuous-flow engine: completes body.lead_id's
    current task (same LeadActivityLog write / focus-session end as POST
    /leads/{id}/complete-task — see complete_lead_task() in
    workday_engine.py) and, in the same request, hands back whichever lead
    is most worth working on next — so the frontend never has to round-trip
    back to the dashboard between leads.

    Deliberately does not touch in_focus/focused_by_email for the *next*
    lead the way GET /workday/next does — this is a lighter-weight "what's
    next" suggestion, not another entry point into that lock, so the two
    flows can't fight over who holds focus on a lead."""
    start = time.perf_counter()
    organization_id, user_email = _require_caller(session)

    lead = await db.get(Lead, body.lead_id)
    if lead is None or lead.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Lead not found")

    completed = await complete_lead_task(
        db, lead, organization_id=organization_id, user_email=user_email
    )
    if not completed:
        raise HTTPException(status_code=400, detail="This lead has no next action to complete")

    await db.commit()
    await db.refresh(lead)

    (scored_completed,) = await score_leads(db, [lead])
    next_lead = await get_next_actionable_lead(db, organization_id, exclude_lead_id=body.lead_id)

    return ApiResponse(
        success=True,
        data=WorkdayCompleteAndNextResponse(
            completed_lead_id=body.lead_id,
            completed_lead=scored_completed,
            next_lead=next_lead,
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


# Pool cap on the "ignored yesterday" row fetch (needed for per-lead
# enrichment_data, not just a count) — same rationale as _AT_RISK_POOL_SIZE.
_IGNORED_POOL_SIZE = 500


@router.get("/performance", response_model=ApiResponse[WorkdayPerformanceResponse])
async def get_workday_performance(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[WorkdayPerformanceResponse]:
    """The accountability layer: how much of today's expected work actually
    got done, what's still overdue, what yesterday's neglect is costing,
    and the completion streak — collapsed into one failure_state
    ("on_track"/"at_risk"/"failing") and one accountability_message.

    tasks_expected_today is next_action_due_at <= today (i.e. due by end of
    today — overdue and due-today combined in one query, since "expected
    today" includes anything that should already be done). completion_rate
    is completed/expected (1.0 when nothing was expected — nothing to fail
    at). leads_ignored_yesterday reads current state only, no historical
    snapshot needed: a lead whose next_action_due_at was already in the
    past *before today started* and is still set (not cleared by a
    completion) is, by definition, still unresolved from at least
    yesterday — a strict subset of overdue_tasks.

    Thirteen queries total (two inside _workday_stats, two counts, one
    ignored-leads row fetch for the revenue estimate, two inside
    rank_leads_by_priority for revenue_at_risk/critical_deals, one dedup
    check for the performance-alert notification, two inside
    _compute_money_saved_today for the AI Deal Coach round's money_saved_today,
    one for auto_actions_executed_today's own count, two inside
    compute_revenue_summary() for the Revenue-loop round's
    revenue_generated_today/avg_revenue_per_conversion), none per-row.
    Reuses _count_overdue_tasks and _workday_stats (both already used by
    /next and /summary), plus the same rank_leads_by_priority()/
    _compute_revenue_at_risk()/_compute_deal_risk_summary() pairing GET
    /workday/summary already uses, instead of re-deriving any of this a
    third time."""
    start = time.perf_counter()
    organization_id, user_email = _require_caller(session)
    now = dt.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    tasks_completed_today, streak_days = await _workday_stats(db, organization_id, user_email, now)

    expected_stmt = select(func.count(Lead.id)).where(
        Lead.organization_id == organization_id,
        Lead.deleted_at.is_(None),
        Lead.next_action_due_at.isnot(None),
        Lead.next_action_due_at < today_end,
    )
    tasks_expected_today = (await db.execute(expected_stmt)).scalar_one()
    completion_rate = (
        tasks_completed_today / tasks_expected_today if tasks_expected_today > 0 else 1.0
    )

    overdue_tasks = await _count_overdue_tasks(db, organization_id, now)

    ignored_stmt = (
        select(Lead)
        .where(
            Lead.organization_id == organization_id,
            Lead.deleted_at.is_(None),
            Lead.next_action_due_at.isnot(None),
            Lead.next_action_due_at < today_start,
        )
        .limit(_IGNORED_POOL_SIZE)
    )
    ignored_leads = (await db.execute(ignored_stmt)).scalars().all()
    leads_ignored_yesterday = len(ignored_leads)
    estimated_revenue_lost = sum(get_lead_estimated_value(lead) for lead in ignored_leads)

    at_risk_cutoff = now - timedelta(days=_AT_RISK_STALE_AFTER_DAYS)
    ranked = await rank_leads_by_priority(db, organization_id)
    revenue_at_risk = _compute_revenue_at_risk(ranked, now=now, stale_cutoff=at_risk_cutoff)
    _money_at_risk_today, critical_deals = _compute_deal_risk_summary(ranked)
    money_saved_today = await _compute_money_saved_today(db, organization_id, today_start)
    auto_actions_executed_today = await _count_auto_actions_today(db, organization_id, today_start)
    (
        response_rate_today,
        responses_received_today,
        avg_response_time_today,
        fast_responses_today,
    ) = await _compute_response_metrics_today(
        db, organization_id, today_start
    )
    # Revenue-loop round — the accountability layer's own "here's the money
    # you actually closed today" plus the all-time average deal size.
    revenue_generated_today, avg_revenue_per_conversion = await compute_revenue_summary(
        db, organization_id, today_start=today_start
    )

    failure_state = detect_user_failure_state(
        completion_rate=completion_rate, overdue_tasks=overdue_tasks
    )
    accountability_message = generate_accountability_message(
        failure_state=failure_state,
        completion_rate=completion_rate,
        overdue_tasks=overdue_tasks,
        leads_ignored_yesterday=leads_ignored_yesterday,
        estimated_revenue_lost=estimated_revenue_lost,
        tasks_remaining_today=max(tasks_expected_today - tasks_completed_today, 0),
    )

    if failure_state == "failing":
        notified = await maybe_notify_performance_alert(
            db,
            organization_id=organization_id,
            user_email=user_email,
            message=accountability_message,
            now=now,
        )
        if notified:
            await db.commit()

    return ApiResponse(
        success=True,
        data=WorkdayPerformanceResponse(
            tasks_completed_today=tasks_completed_today,
            tasks_expected_today=tasks_expected_today,
            completion_rate=completion_rate,
            overdue_tasks=overdue_tasks,
            leads_ignored_yesterday=leads_ignored_yesterday,
            estimated_revenue_lost=estimated_revenue_lost,
            streak_days=streak_days,
            failure_state=failure_state,
            accountability_message=accountability_message,
            revenue_at_risk=revenue_at_risk,
            critical_deals=critical_deals,
            money_saved_today=money_saved_today,
            auto_actions_executed_today=auto_actions_executed_today,
            response_rate_today=response_rate_today,
            responses_received_today=responses_received_today,
            avg_response_time_today=avg_response_time_today,
            fast_responses_today=fast_responses_today,
            revenue_generated_today=revenue_generated_today,
            avg_revenue_per_conversion=avg_revenue_per_conversion,
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/target", response_model=ApiResponse[WorkdayTargetResponse])
async def get_workday_target(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[WorkdayTargetResponse]:
    """Daily gamification target — a fixed default (_DEFAULT_DAILY_TARGET,
    no per-user/org customization yet) matched against the same
    tasks_completed_today _workday_stats() already computes for GET
    /workday/next and .../performance.

    Autonomous-sales-OS round adds a second, revenue-based target
    alongside the task-count one above (additive — see
    WorkdayTargetResponse's own docstring for why this doesn't replace the
    original fields the prompt's literal wording asked for). Four queries
    total: two inside _workday_stats, two inside
    _compute_daily_target_revenue, plus rank_leads_by_priority()'s own
    (reused for current_expected via _sum_today_potential_revenue, the
    same figure WorkdaySummaryResponse.today_potential_revenue already
    computes — no new aggregation logic)."""
    start = time.perf_counter()
    organization_id, user_email = _require_caller(session)
    now = dt.now(timezone.utc)

    completed_today, _streak_days = await _workday_stats(db, organization_id, user_email, now)
    remaining = max(_DEFAULT_DAILY_TARGET - completed_today, 0)
    progress = (
        min(completed_today / _DEFAULT_DAILY_TARGET, 1.0) if _DEFAULT_DAILY_TARGET > 0 else 1.0
    )

    revenue_cutoff = now - timedelta(days=_DAILY_TARGET_REVENUE_WINDOW_DAYS)
    daily_target_revenue = await _compute_daily_target_revenue(db, organization_id, revenue_cutoff)
    ranked = await rank_leads_by_priority(db, organization_id)
    current_expected = _sum_today_potential_revenue(ranked, now=now)
    gap = daily_target_revenue - current_expected
    acceleration_mode = gap > _ACCELERATION_MODE_GAP_THRESHOLD

    return ApiResponse(
        success=True,
        data=WorkdayTargetResponse(
            daily_target=_DEFAULT_DAILY_TARGET,
            completed_today=completed_today,
            remaining=remaining,
            progress=progress,
            daily_target_revenue=daily_target_revenue,
            current_expected=current_expected,
            gap=gap,
            acceleration_mode=acceleration_mode,
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )
