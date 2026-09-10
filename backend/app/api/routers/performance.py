import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_session
from app.api.dependencies.common import get_db, get_request_id
from app.api.responses.api_response import ApiResponse
from app.core.config import settings
from app.models.leads.lead_activity_log import LeadActivityLog
from app.schemas.performance import (
    LeaderboardEntry,
    PressureStateResponse,
    TeamSummaryResponse,
    UserPerformanceResponse,
)
from app.services.leads.team_performance import (
    PRESSURE_MESSAGE_BY_STATE,
    compute_user_performance,
    compute_user_pressure_state,
    maybe_notify_underperformance,
    maybe_notify_user_pressure,
    rank_user_performance,
    reassign_leads_if_needed,
    reassignment_check_due,
    score_org_leads,
)

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/performance", tags=["Performance"])


def _require_organization(session: dict) -> str:
    organization_id = session.get("organization_id")
    if organization_id is None:
        raise HTTPException(status_code=403, detail="Your account isn't part of an organization")
    return organization_id


async def _count_converted_today(db: AsyncSession, organization_id: str, now: datetime) -> int:
    """Distinct leads with a "lead_won" LeadActivityLog entry (the precise
    conversion-moment marker PATCH /leads/{id}/status writes) created
    today — same event compute_revenue_summary()'s own revenue_generated_today
    reads (scoring.py), just counted instead of summed."""
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = select(func.count(func.distinct(LeadActivityLog.lead_id))).where(
        LeadActivityLog.organization_id == organization_id,
        LeadActivityLog.event_type == "lead_won",
        LeadActivityLog.created_at >= today_start,
    )
    return (await db.execute(stmt)).scalar_one()


@router.get("/leaderboard", response_model=ApiResponse[list[LeaderboardEntry]])
async def get_leaderboard(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[LeaderboardEntry]]:
    """Leaderboard Engine (Task 2) — every team member (Lead.owner_email
    with at least one lead in this org) ranked by rank_user_performance()
    (team_performance.py): revenue_converted DESC, response_rate DESC,
    avg_response_time_minutes ASC. Also runs maybe_notify_underperformance()
    (Task 5), maybe_notify_user_pressure() (Sales Pressure Engine, final
    round), and, gated behind reassignment_check_due()'s own cooldown,
    reassign_leads_if_needed() (Task 4; continuous upgrade, final round)
    over the same already-computed performances/scored leads, zero extra
    score_leads() pass — this endpoint doubles as the read AND the trigger
    for all three side effects, same "GET also fires side-effect
    notifications" pattern GET /workday/summary already established."""
    start = time.perf_counter()
    organization_id = _require_organization(session)
    now = datetime.now(timezone.utc)

    scored_leads = await score_org_leads(db, organization_id)
    performances = await compute_user_performance(db, organization_id, leads=scored_leads)
    ranked = rank_user_performance(performances)

    notified = await maybe_notify_underperformance(
        db, organization_id=organization_id, performances=performances, now=now
    )
    pressure_notified = await maybe_notify_user_pressure(
        db, organization_id=organization_id, performances=performances, now=now
    )
    reassigned = 0
    if reassignment_check_due(organization_id, now):
        reassigned = await reassign_leads_if_needed(
            db, organization_id=organization_id, leads=scored_leads, user_performance=performances
        )
    if notified or pressure_notified or reassigned:
        await db.commit()

    return ApiResponse(
        success=True,
        data=[
            LeaderboardEntry(
                user_id=performance.user_id,
                name=performance.name,
                revenue_converted=performance.revenue_converted,
                response_rate=performance.response_rate,
                avg_response_time_minutes=performance.avg_response_time_minutes,
                position=position,
                commission_estimate=performance.commission_estimate,
                badges=performance.badges,
                deals_closed=performance.deals_closed,
                revenue_today=performance.revenue_today,
                revenue_this_week=performance.revenue_this_week,
                pipeline_value=performance.pipeline_value,
            )
            for position, performance in enumerate(ranked, start=1)
        ],
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/user", response_model=ApiResponse[list[UserPerformanceResponse]])
async def get_user_performance(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[UserPerformanceResponse]]:
    """User Performance Tracking (Task 1) — the full per-user metric set
    (compute_user_performance(), team_performance.py) behind its own
    endpoint, for anything that needs more than the leaderboard's own
    narrower per-row shape (e.g. a future per-user profile view)."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    performances = await compute_user_performance(db, organization_id)

    return ApiResponse(
        success=True,
        data=performances,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/team-summary", response_model=ApiResponse[TeamSummaryResponse])
async def get_team_summary(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TeamSummaryResponse]:
    """Team Performance Summary (Task 6) — the org-wide roll-up of
    compute_user_performance()'s own per-user list, plus one extra count
    query for total_converted_today (a distinct-lead count, not a revenue
    sum — nothing else in this codebase already carries that specific
    figure)."""
    start = time.perf_counter()
    organization_id = _require_organization(session)
    now = datetime.now(timezone.utc)

    performances = await compute_user_performance(db, organization_id)
    total_revenue = sum(performance.revenue_converted for performance in performances)
    total_at_risk = sum(performance.revenue_at_risk for performance in performances)
    avg_response_rate = (
        round(sum(performance.response_rate for performance in performances) / len(performances), 1)
        if performances
        else 0.0
    )
    total_converted_today = await _count_converted_today(db, organization_id, now)

    ranked = rank_user_performance(performances)
    top_performer_name = ranked[0].name if ranked else None
    worst_performer_name = ranked[-1].name if ranked else None

    return ApiResponse(
        success=True,
        data=TeamSummaryResponse(
            total_revenue=total_revenue,
            total_converted_today=total_converted_today,
            total_at_risk=total_at_risk,
            avg_response_rate=avg_response_rate,
            top_performer_name=top_performer_name,
            worst_performer_name=worst_performer_name,
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/pressure-state", response_model=ApiResponse[PressureStateResponse])
async def get_pressure_state(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[PressureStateResponse]:
    """Sales Pressure Engine (Task 1, final round) — the calling user's
    own compute_user_pressure_state() classification, for the frontend's
    per-user pressure banner (Task 8.1): "leader"/"neutral"/"at_risk"/
    "underperforming" plus the same ready-to-render sentence
    maybe_notify_user_pressure()'s own notification would carry. Read-
    only — this endpoint never stages a notification itself (that's
    GET /performance/leaderboard's own side effect); it just classifies
    and returns. "neutral" (with team_size < 2, or genuinely average
    otherwise) whenever the calling user isn't in this org's own
    performances at all (no leads owned) — same "no data, no verdict"
    rule this codebase's other learned fields already follow."""
    start = time.perf_counter()
    organization_id = _require_organization(session)
    user_email = session.get("email")

    performances = await compute_user_performance(db, organization_id)
    own_performance = next((p for p in performances if p.user_id == user_email), None)

    if own_performance is None or len(performances) < 2:
        state = "neutral"
    else:
        ranked = rank_user_performance(performances)
        rank = next(
            position for position, p in enumerate(ranked, start=1) if p.user_id == user_email
        )
        avg_revenue = sum(p.revenue_converted for p in performances) / len(performances)
        response_times = [
            p.avg_response_time_minutes for p in performances if p.avg_response_time_minutes is not None
        ]
        avg_response_time = sum(response_times) / len(response_times) if response_times else None
        avg_pipeline_value = sum(p.pipeline_value for p in performances) / len(performances)

        state = compute_user_pressure_state(
            own_performance,
            rank=rank,
            team_size=len(performances),
            avg_revenue_converted=avg_revenue,
            avg_response_time_minutes=avg_response_time,
            avg_pipeline_value=avg_pipeline_value,
        )

    return ApiResponse(
        success=True,
        data=PressureStateResponse(state=state, message=PRESSURE_MESSAGE_BY_STATE[state]),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )
