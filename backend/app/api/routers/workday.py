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
from app.schemas.workday import WorkdayNextResponse
from app.services.leads.scoring import score_leads

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/workday", tags=["Workday"])

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
