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
from app.schemas.performance import LeaderboardEntry, TeamSummaryResponse, UserPerformanceResponse
from app.services.leads.team_performance import (
    compute_user_performance,
    maybe_notify_underperformance,
    rank_user_performance,
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
    (Task 5) over the same already-computed performances, zero extra
    query — this endpoint doubles as the read AND the trigger for that
    pressure notification, same "GET also fires side-effect notifications"
    pattern GET /workday/summary already established."""
    start = time.perf_counter()
    organization_id = _require_organization(session)
    now = datetime.now(timezone.utc)

    performances = await compute_user_performance(db, organization_id)
    ranked = rank_user_performance(performances)

    notified = await maybe_notify_underperformance(
        db, organization_id=organization_id, performances=performances, now=now
    )
    if notified:
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
