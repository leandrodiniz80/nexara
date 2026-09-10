import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_session
from app.api.dependencies.common import get_db, get_request_id
from app.api.responses.api_response import ApiResponse
from app.core.config import settings
from app.schemas.intelligence import (
    AggressionLevelResponse,
    ExecInsightResponse,
    GlobalStrategyResponse,
    RevenueLeaksResponse,
    RevenueSimulationResponse,
)
from app.services.leads.intelligence import generate_exec_insight
from app.services.leads.scoring import (
    compute_action_effectiveness,
    compute_adaptive_weights,
    compute_aggression_level,
    compute_channel_ab_performance,
    compute_global_strategy,
    compute_response_metrics,
    compute_revenue_attribution,
    compute_revenue_mode,
    compute_segment_strategy,
    detect_revenue_leaks,
    rank_leads_by_priority,
    simulate_revenue_if_all_actions_executed,
    top_revenue_bucket,
)
from app.services.leads.team_performance import compute_user_performance
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
    revenue_attribution = await compute_revenue_attribution(db, organization_id)
    weights = await compute_adaptive_weights(
        db,
        organization_id,
        action_effectiveness=action_effectiveness,
        revenue_attribution=revenue_attribution,
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


@router.get("/global-strategy", response_model=ApiResponse[GlobalStrategyResponse])
async def get_global_strategy(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[GlobalStrategyResponse]:
    """Global Strategy Engine (Task 2/8, final round) —
    compute_global_strategy() (scoring.py) fed by compute_response_
    metrics()'s own all-time response_rate, compute_revenue_attribution()'s
    own top_revenue_action, and this org's own current team performance
    (compute_user_performance(), team_performance.py) — three already-
    cheap, already-established aggregates, no new heavy query."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    ranked = await rank_leads_by_priority(db, organization_id)
    response_metrics = await compute_response_metrics(db, organization_id)
    revenue_attribution = await compute_revenue_attribution(db, organization_id)
    top_revenue_action = top_revenue_bucket(revenue_attribution.revenue_by_action)
    team_performance = await compute_user_performance(db, organization_id)

    strategy = compute_global_strategy(
        ranked,
        response_rate=response_metrics.response_rate,
        top_revenue_action=top_revenue_action,
        team_performance=team_performance,
    )

    return ApiResponse(
        success=True,
        data=GlobalStrategyResponse(**strategy),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/aggression-level", response_model=ApiResponse[AggressionLevelResponse])
async def get_aggression_level(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[AggressionLevelResponse]:
    """Dynamic Aggression Mode (Task 3/8, final round) —
    compute_aggression_level() (scoring.py) fed by compute_lost_
    opportunity_today() and simulate_revenue_if_all_actions_executed(),
    both over the same rank_leads_by_priority() candidate pool this
    router's own revenue-simulation endpoint already reads."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    ranked = await rank_leads_by_priority(db, organization_id)
    lost_opportunity_today = compute_lost_opportunity_today(ranked)
    simulation = simulate_revenue_if_all_actions_executed(ranked)

    level = compute_aggression_level(
        lost_opportunity_today=lost_opportunity_today,
        current_expected=simulation["current_expected"],
        delta=simulation["delta"],
    )
    revenue_mode = compute_revenue_mode(level)

    return ApiResponse(
        success=True,
        data=AggressionLevelResponse(level=level, revenue_mode=revenue_mode),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/channel-ab-performance", response_model=ApiResponse[dict[str, dict]])
async def get_channel_ab_performance(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, dict]]:
    """A/B Test Engine (Task 4/8, final round) —
    compute_channel_ab_performance() (scoring.py) over the same
    ActionEffectivenessResponse/RevenueAttributionResponse this router's
    own /adaptive-weights endpoint already computes, no new query. Keyed
    call_now/send_message/schedule_meeting, each with conversion_rate/
    revenue/score."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    action_effectiveness = await compute_action_effectiveness(db, organization_id)
    revenue_attribution = await compute_revenue_attribution(db, organization_id)
    performance = compute_channel_ab_performance(action_effectiveness, revenue_attribution)

    return ApiResponse(
        success=True,
        data=performance,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/segment-strategy", response_model=ApiResponse[dict[str, dict]])
async def get_segment_strategy(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, dict]]:
    """Segment Strategy Engine (Task 5/8, final round) —
    compute_segment_strategy()'s own dict straight through (scoring.py),
    the same per-segment recommendation compute_action_type_and_urgency()
    itself already applies (score_leads() computes and threads this
    through on every read). Exposed here purely for visibility."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    strategy = await compute_segment_strategy(db, organization_id)

    return ApiResponse(
        success=True,
        data=strategy,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/revenue-leaks", response_model=ApiResponse[RevenueLeaksResponse])
async def get_revenue_leaks(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[RevenueLeaksResponse]:
    """Revenue Leak Detector (Task 5/8, final round) —
    detect_revenue_leaks() (scoring.py) over the same rank_leads_by_
    priority() candidate pool every other endpoint in this router already
    reads, zero new query."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    ranked = await rank_leads_by_priority(db, organization_id)
    leaks = detect_revenue_leaks(ranked)

    return ApiResponse(
        success=True,
        data=RevenueLeaksResponse(**leaks),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/exec-insight", response_model=ApiResponse[ExecInsightResponse])
async def get_exec_insight(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ExecInsightResponse]:
    """CEO Insight Layer (Task 6/7/8, final round) — generate_exec_insight()
    (services/leads/intelligence.py) now also fed by compute_aggression_
    level(), compute_global_strategy(), and detect_revenue_leaks() (Task 7
    upgrade), all sharing the exact same rank_leads_by_priority()/
    compute_response_metrics()/compute_revenue_attribution()/
    compute_user_performance() calls this router's own other three
    endpoints already make — one request here costs the same as calling
    /global-strategy + /aggression-level + /revenue-leaks separately, just
    bundled into one narrative sentence."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    ranked = await rank_leads_by_priority(db, organization_id)
    lost_opportunity_today = compute_lost_opportunity_today(ranked)
    simulation = simulate_revenue_if_all_actions_executed(ranked)

    response_metrics = await compute_response_metrics(db, organization_id)
    revenue_attribution = await compute_revenue_attribution(db, organization_id)
    top_revenue_action = top_revenue_bucket(revenue_attribution.revenue_by_action)
    team_performance = await compute_user_performance(db, organization_id)
    global_strategy = compute_global_strategy(
        ranked,
        response_rate=response_metrics.response_rate,
        top_revenue_action=top_revenue_action,
        team_performance=team_performance,
    )

    aggression_level = compute_aggression_level(
        lost_opportunity_today=lost_opportunity_today,
        current_expected=simulation["current_expected"],
        delta=simulation["delta"],
    )

    revenue_leaks = detect_revenue_leaks(ranked)

    message = generate_exec_insight(
        lost_opportunity_today=lost_opportunity_today,
        simulation=simulation,
        aggression_level=aggression_level,
        global_strategy=global_strategy,
        revenue_leaks=revenue_leaks,
    )

    return ApiResponse(
        success=True,
        data=ExecInsightResponse(message=message),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )
