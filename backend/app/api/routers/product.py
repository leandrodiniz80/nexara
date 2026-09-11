import time
from datetime import datetime as dt
from datetime import timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_session
from app.api.dependencies.common import get_db, get_request_id
from app.api.responses.api_response import ApiResponse
from app.core.config import settings
from app.schemas.product import ProductSummaryResponse
from app.services.leads.intelligence import compute_global_decision, compute_product_summary
from app.services.leads.scoring import (
    compute_aggression_level,
    rank_leads_by_priority,
    simulate_revenue_if_all_actions_executed,
)
from app.services.leads.workday_engine import (
    AT_RISK_STALE_AFTER_DAYS,
    DAILY_TARGET_REVENUE_WINDOW_DAYS,
    build_action_queue,
    compute_daily_target_revenue,
    compute_lost_opportunity_today,
    compute_revenue_at_risk,
    derive_required_action_and_reason,
    get_next_mandatory_lead,
    sum_today_potential_revenue,
)

# PRIMARY ENDPOINT — product-consolidation round. Everything under
# /workday/*, /intelligence/*, and /revenue/* remains the advanced/detail
# layer this router's own single endpoint is assembled from; nothing here
# recomputes any of that logic, it only aggregates already-computed
# figures (see compute_product_summary()'s own docstring,
# services/leads/intelligence.py).
router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/product", tags=["Product"])


def _require_organization(session: dict) -> str:
    organization_id = session.get("organization_id")
    if organization_id is None:
        raise HTTPException(status_code=403, detail="Your account isn't part of an organization")
    return organization_id


@router.get("/summary", response_model=ApiResponse[ProductSummaryResponse])
async def get_product_summary(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ProductSummaryResponse]:
    """PRIMARY ENDPOINT of the Revenue Decision System (Tasks 2/3,
    product-consolidation round) — the single source of truth the whole
    product can be explained from in seconds. One rank_leads_by_priority()
    call is reused for every figure below (revenue_today_expected,
    revenue_at_risk, lost_opportunity_today, the aggression level, the
    mandatory-lead decision, and biggest_opportunity all read off the same
    `ranked` list); the only other query this endpoint pays for is
    compute_daily_target_revenue()'s own pair, the exact same one GET
    /workday/target already pays for revenue_today_gap (Task 6 — no
    additional heavy queries beyond what those two existing endpoints
    already cost individually).

    next_action/execution_blocked come from compute_global_decision(),
    which is itself built from GET /workday/enforcement-state's own
    mandatory-lead pipeline (build_action_queue()+get_next_mandatory_lead()
    +derive_required_action_and_reason(), workday_engine.py) — so this
    endpoint's decision can never disagree with that one (Task 5)."""
    start = time.perf_counter()
    organization_id = _require_organization(session)
    now = dt.now(timezone.utc)

    ranked = await rank_leads_by_priority(db, organization_id)

    revenue_today_expected = sum_today_potential_revenue(ranked, now=now)
    at_risk_cutoff = now - timedelta(days=AT_RISK_STALE_AFTER_DAYS)
    revenue_at_risk = compute_revenue_at_risk(ranked, now=now, stale_cutoff=at_risk_cutoff)

    revenue_cutoff = now - timedelta(days=DAILY_TARGET_REVENUE_WINDOW_DAYS)
    daily_target_revenue = await compute_daily_target_revenue(db, organization_id, revenue_cutoff)
    revenue_today_gap = daily_target_revenue - revenue_today_expected

    lost_opportunity_today = compute_lost_opportunity_today(ranked)
    simulation = simulate_revenue_if_all_actions_executed(ranked)
    aggression_level = compute_aggression_level(
        lost_opportunity_today=lost_opportunity_today,
        current_expected=simulation["current_expected"],
        delta=simulation["delta"],
    )

    queue = build_action_queue(ranked)
    mandatory_lead = get_next_mandatory_lead(queue)
    required_action = reason = None
    if mandatory_lead is not None:
        required_action, reason = derive_required_action_and_reason(mandatory_lead)

    decision = compute_global_decision(
        mandatory_lead=mandatory_lead,
        required_action=required_action,
        reason=reason,
        aggression_level=aggression_level,
    )

    summary = compute_product_summary(
        ranked,
        revenue_today_expected=revenue_today_expected,
        revenue_today_gap=revenue_today_gap,
        revenue_at_risk=revenue_at_risk,
        decision=decision,
    )

    return ApiResponse(
        success=True,
        data=ProductSummaryResponse(**summary),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )
