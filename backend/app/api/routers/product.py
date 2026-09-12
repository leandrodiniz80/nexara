import time
from datetime import datetime as dt
from datetime import timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_session
from app.api.dependencies.common import get_db, get_request_id
from app.api.responses.api_response import ApiResponse
from app.core.config import settings
from app.models.leads.lead_activity_log import LeadActivityLog
from app.schemas.product import ProductSummaryResponse
from app.services.leads.intelligence import (
    compute_decision_score,
    compute_dynamic_kpis,
    compute_efficiency_mode,
    compute_failure_patterns,
    compute_global_decision,
    compute_main_action,
    compute_next_best_move,
    compute_pressure_message,
    compute_product_mode,
    compute_product_summary,
    compute_required_actions,
    compute_revenue_efficiency,
    compute_revenue_gap,
    compute_sales_readiness,
    compute_system_health,
    simplify_system_state,
)
from app.services.leads.scoring import (
    apply_failure_corrections,
    compute_aggression_level,
    compute_conversion_insights,
    compute_response_metrics,
    detect_revenue_leaks,
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

# _fetch_failure_pattern_rows()'s own window/cap (self-optimizing-revenue-
# brain round) — the one genuinely new query this endpoint pays for: no
# existing aggregate joins lead_lost against the action_* events that
# preceded it. Bounded the same "steady window, capped rows" way
# compute_response_metrics()'s own window and rank_leads_by_priority()'s
# own _PRIORITY_CANDIDATE_POOL_SIZE already are (scoring.py).
_FAILURE_PATTERN_WINDOW_DAYS = 90
_FAILURE_PATTERN_ROW_LIMIT = 2000


def _require_organization(session: dict) -> str:
    organization_id = session.get("organization_id")
    if organization_id is None:
        raise HTTPException(status_code=403, detail="Your account isn't part of an organization")
    return organization_id


async def _fetch_failure_pattern_rows(db: AsyncSession, organization_id: str, *, cutoff: dt) -> list[dict]:
    """One bounded query backing compute_failure_patterns()'s own
    activities["rows"] (services/leads/intelligence.py) — lead_lost +
    action_call/action_message/action_meeting LeadActivityLog rows, the
    only two event families that function needs and no existing aggregate
    already joins."""
    stmt = (
        select(
            LeadActivityLog.lead_id,
            LeadActivityLog.event_type,
            LeadActivityLog.created_at,
            LeadActivityLog.duration_seconds,
        )
        .where(
            LeadActivityLog.organization_id == organization_id,
            LeadActivityLog.event_type.in_(
                ("lead_lost", "action_call", "action_message", "action_meeting")
            ),
            LeadActivityLog.created_at >= cutoff,
        )
        .order_by(LeadActivityLog.created_at.asc())
        .limit(_FAILURE_PATTERN_ROW_LIMIT)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "lead_id": row.lead_id,
            "event_type": row.event_type,
            "created_at": row.created_at,
            "duration_seconds": row.duration_seconds,
        }
        for row in rows
    ]


@router.get("/summary", response_model=ApiResponse[ProductSummaryResponse])
async def get_product_summary(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ProductSummaryResponse]:
    """PRIMARY ENDPOINT of the Revenue Decision System (Tasks 2/3,
    product-consolidation round; extended into the sellable Product Layer
    — Tasks 1-6, product-layer round). One rank_leads_by_priority() call is
    reused for every figure below (revenue_today_expected, revenue_at_risk,
    lost_opportunity_today, the aggression level, the mandatory-lead
    decision, biggest_opportunity, product_mode, and sales_readiness_score
    all read off the same `ranked` list); the only other queries this
    endpoint pays for are compute_daily_target_revenue()'s own pair (the
    exact same one GET /workday/target already pays, for revenue_today_gap
    and the product layer's own daily_target_revenue KPI) and
    compute_response_metrics()'s own single query (the same
    already-established aggregate GET /intelligence/global-strategy already
    reuses) for sales_readiness's response-rate component — no other new
    query anywhere in this endpoint.

    next_action/execution_blocked come from compute_global_decision(),
    which is itself built from GET /workday/enforcement-state's own
    mandatory-lead pipeline (build_action_queue()+get_next_mandatory_lead()
    +derive_required_action_and_reason(), workday_engine.py) — so this
    endpoint's decision can never disagree with that one (Task 5, product-
    consolidation round). product_mode/kpis/sales_readiness_score/
    main_action/system_state are all pure aggregation over these same
    already-computed signals (see compute_product_mode()/compute_dynamic_
    kpis()/compute_sales_readiness()/compute_main_action()/simplify_
    system_state(), services/leads/intelligence.py) — no per-industry
    logic anywhere, so this reads correctly for any vertical this tenant
    happens to sell into.

    Revenue Command Center round adds revenue_gap/decision_score/
    required_actions_today/required_calls_today/required_messages_today/
    pressure_message — still zero new queries, all derived from `signals`
    (which now also carries revenue_gap once compute_revenue_gap() runs)
    and `kpis` (see compute_revenue_gap()/compute_required_actions()/
    compute_decision_score()/compute_pressure_message(), same module).
    compute_main_action() was replaced this round to name real leads by
    count and value instead of a generic sentence — see its own
    docstring."""
    start = time.perf_counter()
    organization_id = _require_organization(session)
    now = dt.now(timezone.utc)

    ranked = await rank_leads_by_priority(db, organization_id)

    # Self-Optimizing Revenue Brain (self-optimizing-revenue-brain round)
    # — failure_patterns is computed before anything else reads `ranked`
    # so apply_failure_corrections() (scoring.py) can correct every lead's
    # score/urgency in place, the same "apply_*_override, don't rewrite
    # compute_lead_score()" precedent apply_strategy_override() already
    # uses. Two new queries total: compute_conversion_insights()'s own two
    # (already-established, reused verbatim for top_loss_reason — not
    # re-parsed) and _fetch_failure_pattern_rows()'s own one bounded query.
    failure_pattern_cutoff = now - timedelta(days=_FAILURE_PATTERN_WINDOW_DAYS)
    conversion_insights = await compute_conversion_insights(db, organization_id)
    failure_pattern_rows = await _fetch_failure_pattern_rows(
        db, organization_id, cutoff=failure_pattern_cutoff
    )
    failure_patterns = compute_failure_patterns(
        ranked,
        {"top_loss_reason": conversion_insights.top_loss_reason, "rows": failure_pattern_rows},
    )
    ranked = [apply_failure_corrections(lead, failure_patterns) for lead in ranked]

    open_leads = [lead for lead in ranked if lead.status not in ("converted", "lost")]

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

    # Product layer (Tasks 1-6, product-layer round) — all pure aggregation
    # over the same `ranked` pool plus two already-established aggregates
    # (compute_response_metrics, detect_revenue_leaks), no new heavy query.
    response_metrics = await compute_response_metrics(db, organization_id)
    leaks = detect_revenue_leaks(ranked)
    current_expected = simulation["current_expected"]
    optimized_expected = simulation["optimized_expected"]
    execution_rate = (current_expected / optimized_expected * 100) if optimized_expected > 0 else 100.0

    signals = {
        "revenue_today_expected": revenue_today_expected,
        "revenue_today_gap": revenue_today_gap,
        "revenue_today_possible": revenue_today_expected,
        "current_expected": current_expected,
        "daily_target_revenue": daily_target_revenue,
        "response_rate": response_metrics.response_rate,
        "execution_rate": execution_rate,
        "total_open_leads": len(open_leads),
        "overdue_count": sum(1 for lead in open_leads if lead.is_overdue),
        "high_value_leads_without_action": leaks["high_value_leads_without_action"],
        "next_action": decision["next_action"],
    }

    product_mode = compute_product_mode(ranked, signals, performance=None)
    kpis = compute_dynamic_kpis(product_mode, signals)
    sales_readiness_score = compute_sales_readiness(signals, performance=None, leaks=leaks)

    # Revenue Command Center (revenue-command-center round) — revenue_gap
    # feeds both compute_required_actions() and compute_decision_score(),
    # so it's threaded into `signals` before either runs.
    revenue_gap = compute_revenue_gap(signals, kpis)
    signals["revenue_gap"] = revenue_gap
    required_actions = compute_required_actions(signals, {"revenue_gap": revenue_gap}, kpis)
    decision_score = compute_decision_score(signals)

    summary["product_mode"] = product_mode
    summary["sales_readiness_score"] = sales_readiness_score
    summary["decision_score"] = decision_score
    summary["kpis"] = kpis
    summary["main_action"] = compute_main_action(ranked)
    summary["system_state"] = simplify_system_state(summary)
    summary["revenue_today_possible"] = revenue_today_expected
    summary["next_best_action"] = decision["next_action"]
    summary["top_priority_lead_id"] = (
        summary["biggest_opportunity"]["lead_id"] if summary["biggest_opportunity"] else None
    )
    summary["revenue_gap"] = revenue_gap
    summary["required_actions_today"] = required_actions["required_actions_today"]
    summary["required_calls_today"] = required_actions["required_calls_today"]
    summary["required_messages_today"] = required_actions["required_messages_today"]
    summary["pressure_message"] = compute_pressure_message(summary)

    # Self-Optimizing Revenue Brain (self-optimizing-revenue-brain round)
    # — efficiency/health are pure aggregation over `ranked` (already
    # corrected above) and `summary`'s own already-computed scores, zero
    # further queries.
    efficiency = compute_revenue_efficiency(ranked)
    efficiency_mode = compute_efficiency_mode(efficiency)
    system_health = compute_system_health(summary, efficiency)

    summary["efficiency_mode"] = efficiency_mode
    summary["next_best_move"] = compute_next_best_move(summary, failure_patterns, efficiency_mode)
    summary["system_health"] = system_health["health_score"]
    summary["system_status"] = system_health["status"]
    summary["failure_pattern_detected"] = bool(
        failure_patterns.get("top_loss_reason") or failure_patterns.get("worst_channel")
    )

    return ApiResponse(
        success=True,
        data=ProductSummaryResponse(**summary),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )
