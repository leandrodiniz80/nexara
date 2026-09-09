import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_session
from app.api.dependencies.common import get_db, get_request_id
from app.api.responses.api_response import ApiResponse
from app.core.config import settings
from app.schemas.intelligence import ExecInsightResponse, RevenueSimulationResponse
from app.services.leads.intelligence import generate_exec_insight
from app.services.leads.scoring import (
    compute_action_effectiveness,
    compute_adaptive_weights,
    rank_leads_by_priority,
    simulate_revenue_if_all_actions_executed,
)
from app.services.leads.workday_engine import compute_lost_opportunity_today

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/intelligence", tags=["Intelligence"])


def _require_organization(session: dict) -> str:
    organization_id = session.get("organization_id")
    if organization_id is None:
        raise HTTPException(status_code=403, detail="Your account isn't part of an organization")
    return organization_id


@router.get("/adaptive-weights", response_model=ApiResponse[dict[str, float]])
async def get_adaptive_weights(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, float]]:
    """Adaptive Scoring Weights (Task 1/7, Adaptive Intelligence round) —
    compute_adaptive_weights()'s own dict straight through (scoring.py),
    the same values compute_lead_score() itself already applies to its
    matching bonuses. Exposed here purely for visibility/debugging (e.g.
    a future Learning Panel entry) — nothing here feeds back into scoring
    beyond what score_leads() already does on every read."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    action_effectiveness = await compute_action_effectiveness(db, organization_id)
    weights = await compute_adaptive_weights(
        db, organization_id, action_effectiveness=action_effectiveness
    )

    return ApiResponse(
        success=True,
        data=weights,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/revenue-simulation", response_model=ApiResponse[RevenueSimulationResponse])
async def get_revenue_simulation(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[RevenueSimulationResponse]:
    """Revenue Simulation Engine (Task 5/7, Adaptive Intelligence round) —
    simulate_revenue_if_all_actions_executed() (scoring.py) over the same
    candidate pool rank_leads_by_priority() already scores for GET
    /leads/priority, no new candidate query beyond that."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    ranked = await rank_leads_by_priority(db, organization_id)
    simulation = simulate_revenue_if_all_actions_executed(ranked)

    return ApiResponse(
        success=True,
        data=RevenueSimulationResponse(**simulation),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/exec-insight", response_model=ApiResponse[ExecInsightResponse])
async def get_exec_insight(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ExecInsightResponse]:
    """CEO Insight Layer (Task 6/7, Adaptive Intelligence round) —
    generate_exec_insight() (services/leads/intelligence.py) fed by the
    same already-scored candidate pool this router's own revenue-simulation
    endpoint reads, plus compute_lost_opportunity_today() (workday_engine.py,
    also used by GET /workday/summary) — one shared rank_leads_by_priority()
    call covers both."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    ranked = await rank_leads_by_priority(db, organization_id)
    lost_opportunity_today = compute_lost_opportunity_today(ranked)
    simulation = simulate_revenue_if_all_actions_executed(ranked)

    message = generate_exec_insight(
        lost_opportunity_today=lost_opportunity_today, simulation=simulation
    )

    return ApiResponse(
        success=True,
        data=ExecInsightResponse(message=message),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )
