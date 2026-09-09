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
from app.schemas.leads.lead import LeadResponse
from app.schemas.workday import (
    WorkdayCompleteAndNextRequest,
    WorkdayCompleteAndNextResponse,
    WorkdayNextResponse,
    WorkdayPerformanceResponse,
    WorkdaySummaryResponse,
    WorkdayTargetResponse,
)
from app.services.leads.enrichment import HIGH_VALUE_LEAD_THRESHOLD, get_lead_estimated_value
from app.services.leads.scoring import rank_leads_by_priority, score_leads
from app.services.leads.workday_engine import (
    complete_lead_task,
    detect_user_failure_state,
    format_brl,
    generate_accountability_message,
    get_next_actionable_lead,
    maybe_notify_critical_deals,
    maybe_notify_high_value_leads,
    maybe_notify_performance_alert,
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

    Six queries total, none per-row (up to 2 more, conditional, only when a
    new high-value or critical-deal alert is actually staged): today/overdue
    are plain COUNTs (backed by ix_leads_org_id_next_action_due_at, same
    index GET /leads/tasks uses); leads-at-risk is the same WHERE shape as
    GET /leads/attention (ix_leads_org_id_status_updated_at), fetched as
    rows (not just a count) since estimated_revenue_at_risk needs each
    one's enrichment_data; high_priority_leads/revenue_at_risk/
    today_potential_revenue/money_at_risk_today/critical_deals_count all
    reuse the one rank_leads_by_priority() call (candidate query +
    score_leads' own one extra query) — the same cost GET /leads/priority
    already pays elsewhere on this same dashboard — plus one dedup check
    each for maybe_notify_high_value_leads()/maybe_notify_critical_deals()."""
    start = time.perf_counter()
    organization_id, _user_email = _require_caller(session)
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
    if notified_count:
        await db.commit()

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
        ),
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

    Ten queries total (two inside _workday_stats, two counts, one
    ignored-leads row fetch for the revenue estimate, two inside
    rank_leads_by_priority for revenue_at_risk/critical_deals, one dedup
    check for the performance-alert notification, two inside
    _compute_money_saved_today for the AI Deal Coach round's money_saved_today),
    none per-row. Reuses _count_overdue_tasks and _workday_stats (both
    already used by /next and /summary), plus the same
    rank_leads_by_priority()/_compute_revenue_at_risk()/
    _compute_deal_risk_summary() pairing GET /workday/summary already uses,
    instead of re-deriving any of this a third time."""
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
    /workday/next and .../performance. Two queries (both inside
    _workday_stats), no new table."""
    start = time.perf_counter()
    organization_id, user_email = _require_caller(session)
    now = dt.now(timezone.utc)

    completed_today, _streak_days = await _workday_stats(db, organization_id, user_email, now)
    remaining = max(_DEFAULT_DAILY_TARGET - completed_today, 0)
    progress = (
        min(completed_today / _DEFAULT_DAILY_TARGET, 1.0) if _DEFAULT_DAILY_TARGET > 0 else 1.0
    )

    return ApiResponse(
        success=True,
        data=WorkdayTargetResponse(
            daily_target=_DEFAULT_DAILY_TARGET,
            completed_today=completed_today,
            remaining=remaining,
            progress=progress,
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )
