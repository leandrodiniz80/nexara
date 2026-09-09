import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_session
from app.api.dependencies.common import get_db, get_request_id
from app.api.responses.api_response import ApiResponse
from app.core.config import settings
from app.models.leads.lead import Lead
from app.models.leads.lead_status_history import LeadStatusHistory
from app.schemas.revenue import RevenueSummaryResponse, RevenueTrendDay
from app.services.leads.enrichment import get_lead_estimated_value
from app.services.leads.scoring import compute_revenue_attribution, score_leads

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/revenue", tags=["Revenue"])

# Same "contacted, no recent touch" definition and default window GET
# /leads/attention and GET /workday/summary's at-risk estimate already use.
# Duplicated here rather than imported from workday.py — these are two
# independent read endpoints, and this round's mandate is zero regression
# on the ones that already ship.
_AT_RISK_STALE_AFTER_DAYS = 3
# Sanity cap on the all-leads row fetch (needed for per-lead enrichment_data,
# not just a count) — same rationale as every other capped candidate pool in
# this codebase: comfortably above any realistic per-org lead count at this
# product stage.
_REVENUE_POOL_SIZE = 2000
_TREND_DAYS = 7
_TREND_POOL_SIZE = 5000


def _require_organization(session: dict) -> str:
    organization_id = session.get("organization_id")
    if organization_id is None:
        raise HTTPException(status_code=403, detail="Your account isn't part of an organization")
    return organization_id


@router.get("/summary", response_model=ApiResponse[RevenueSummaryResponse])
async def get_revenue_summary(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[RevenueSummaryResponse]:
    """Org-wide revenue snapshot: how much is in the pipeline, how much has
    already closed, how much was lost, how much of the open pipeline is
    going cold, and — probability-weighted — what the open pipeline is
    actually forecast to yield. potential/converted/lost/at_risk come from
    get_lead_estimated_value() (raw, unweighted) at read time;
    expected_pipeline_revenue is score_leads()'s own probability-weighted
    expected_value, summed over new+contacted leads.

    Up to seven queries total, none per-row: one capped row-fetch (needed
    for per-lead enrichment_data — potential/converted/lost/at_risk are all
    derived from this single pass over the same rows), two plain COUNTs for
    conversion_rate (accurate regardless of scale, unlike the capped
    revenue pool), score_leads()'s own two queries — reused on the same
    `leads` list already fetched, not a second row-fetch — and
    compute_revenue_attribution()'s own two queries (Revenue-loop round)
    for revenue_by_action, the Revenue Panel's own "breakdown por ação"."""
    start = time.perf_counter()
    organization_id = _require_organization(session)
    now = datetime.now(timezone.utc)
    at_risk_cutoff = now - timedelta(days=_AT_RISK_STALE_AFTER_DAYS)

    leads_stmt = (
        select(Lead)
        .where(Lead.organization_id == organization_id, Lead.deleted_at.is_(None))
        .limit(_REVENUE_POOL_SIZE)
    )
    leads = (await db.execute(leads_stmt)).scalars().all()

    potential_revenue = 0.0
    converted_revenue = 0.0
    lost_revenue = 0.0
    at_risk_revenue = 0.0
    for lead in leads:
        value = get_lead_estimated_value(lead)
        if lead.status == "lost":
            lost_revenue += value
        else:
            potential_revenue += value
        if lead.status == "converted":
            converted_revenue += value
        if lead.status == "contacted" and lead.updated_at < at_risk_cutoff:
            at_risk_revenue += value

    total_count_stmt = select(func.count(Lead.id)).where(
        Lead.organization_id == organization_id, Lead.deleted_at.is_(None)
    )
    total_count = (await db.execute(total_count_stmt)).scalar_one()

    converted_count_stmt = select(func.count(Lead.id)).where(
        Lead.organization_id == organization_id,
        Lead.deleted_at.is_(None),
        Lead.status == "converted",
    )
    converted_count = (await db.execute(converted_count_stmt)).scalar_one()

    conversion_rate = converted_count / total_count if total_count > 0 else 0.0

    # Revenue-intelligence round: the open pipeline's probability-weighted
    # forecast — reuses the same `leads` pool already fetched above, scored
    # once (two more queries, same as every other score_leads() call in
    # this codebase) rather than a second row-fetch.
    scored = await score_leads(db, leads)
    expected_pipeline_revenue = sum(
        response.expected_value for response in scored if response.status in ("new", "contacted")
    )

    # Revenue-loop round — the Revenue Panel's own call/message/meeting
    # breakdown (compute_revenue_attribution(), scoring.py).
    revenue_attribution = await compute_revenue_attribution(db, organization_id)

    return ApiResponse(
        success=True,
        data=RevenueSummaryResponse(
            potential_revenue=potential_revenue,
            converted_revenue=converted_revenue,
            lost_revenue=lost_revenue,
            at_risk_revenue=at_risk_revenue,
            conversion_rate=conversion_rate,
            expected_pipeline_revenue=expected_pipeline_revenue,
            revenue_by_action=revenue_attribution.revenue_by_action,
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/performance-trend", response_model=ApiResponse[list[RevenueTrendDay]])
async def get_revenue_performance_trend(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[RevenueTrendDay]]:
    """Last 7 days of revenue movement: how much came in (created), how
    much closed (converted), how much fell through (lost) — each day's
    figure is the sum of get_lead_estimated_value() over the leads that hit
    that state on that day. "Created" reads Lead.created_at directly;
    "converted"/"lost" read lead_status_history (POST /leads has never
    written a status-history row for a brand-new lead, only PATCH
    .../status does on an actual transition), joined back to Lead for its
    current enrichment_data — a lead's value is always its *current*
    estimate, not a value frozen at the moment it converted.

    Two queries total, both bounded to the 7-day window, neither per-row."""
    start = time.perf_counter()
    organization_id = _require_organization(session)
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_start = today_start - timedelta(days=_TREND_DAYS - 1)

    days = [
        (window_start + timedelta(days=offset)).date().isoformat() for offset in range(_TREND_DAYS)
    ]
    by_day = {day: {"converted": 0.0, "lost": 0.0, "created": 0.0} for day in days}

    created_stmt = (
        select(Lead)
        .where(
            Lead.organization_id == organization_id,
            Lead.deleted_at.is_(None),
            Lead.created_at >= window_start,
        )
        .limit(_TREND_POOL_SIZE)
    )
    created_leads = (await db.execute(created_stmt)).scalars().all()
    for lead in created_leads:
        day_key = lead.created_at.date().isoformat()
        if day_key in by_day:
            by_day[day_key]["created"] += get_lead_estimated_value(lead)

    history_stmt = (
        select(LeadStatusHistory.to_status, LeadStatusHistory.created_at, Lead)
        .join(Lead, Lead.id == LeadStatusHistory.lead_id)
        .where(
            LeadStatusHistory.organization_id == organization_id,
            LeadStatusHistory.to_status.in_(("converted", "lost")),
            LeadStatusHistory.created_at >= window_start,
        )
        .limit(_TREND_POOL_SIZE)
    )
    history_rows = (await db.execute(history_stmt)).all()
    for to_status, changed_at, lead in history_rows:
        day_key = changed_at.date().isoformat()
        if day_key in by_day:
            by_day[day_key][to_status] += get_lead_estimated_value(lead)

    return ApiResponse(
        success=True,
        data=[
            RevenueTrendDay(
                date=day,
                converted=by_day[day]["converted"],
                lost=by_day[day]["lost"],
                created=by_day[day]["created"],
            )
            for day in days
        ],
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )
