import logging
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_session
from app.api.dependencies.common import get_db, get_request_id
from app.api.responses.api_response import ApiResponse
from app.core.config import settings
from app.models.leads.lead import Lead
from app.models.leads.lead_activity_log import LeadActivityLog
from app.services.leads.enrichment import format_brl, simulate_enrichment
from app.services.leads.execution_engine import InvalidLeadAction, execute_lead_action
from app.services.leads.intelligence import (
    FOCUS_BY_NEXT_ACTION,
    compute_decision_score,
    compute_failure_patterns,
    compute_global_decision,
    compute_main_action,
    compute_pressure_message,
    compute_required_actions,
    compute_revenue_gap,
    compute_sales_readiness,
    simplify_system_state,
)
from app.services.leads.scoring import (
    LOSS_REASON_MARKER,
    RESPONSE_EVENT_TYPE_BY_STATE,
    apply_failure_corrections,
    compute_aggression_level,
    compute_response_metrics,
    detect_revenue_leaks,
    rank_leads_by_priority,
    score_leads,
    simulate_revenue_if_all_actions_executed,
)
from app.services.leads.workday_engine import (
    AT_RISK_STALE_AFTER_DAYS,
    DAILY_TARGET_REVENUE_WINDOW_DAYS,
    FAILURE_PATTERN_WINDOW_DAYS,
    build_action_queue,
    compute_daily_target_revenue,
    compute_lost_opportunity_today,
    compute_revenue_at_risk,
    derive_required_action_and_reason,
    fetch_failure_pattern_rows,
    get_next_mandatory_lead,
    sum_today_potential_revenue,
)

# BACKEND-DRIVEN OPERATION LAYER (system round) — lets the product be
# operated, demoed, and sold from the API alone whenever the Next.js
# frontend deployment is unavailable. Every endpoint here reuses existing
# services (score_leads, execute_lead_action, simulate_enrichment) — no
# scoring/execution logic is reimplemented, only thin orchestration and,
# for /demo-seed, direct writes that mirror what POST /leads and PATCH
# /leads/{id}/status already do inline (those two remain untouched;
# extracting their logic into shared functions would mean editing existing
# endpoints, which this round's own hard rules forbid).
router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/system", tags=["System"])
logger = logging.getLogger("app.api.routers.system")

FRONTEND_URL = "https://invigorating-stillness-production-07d1.up.railway.app"
API_URL = "https://nexara-production-4254.up.railway.app"

# validate_system_consistency()'s own opt-in gate (regression-guard round)
# — off unless explicitly turned on, so the check this function runs (see
# its own docstring) never runs in production by accident. Read once at
# import time: consistent with settings.* being read the same way
# elsewhere in this codebase, and this doesn't need to react to an env
# var changing mid-process.
_VALIDATE_CONSISTENCY = (
    settings.ENVIRONMENT.lower() == "debug" or os.getenv("VALIDATE_CONSISTENCY", "").lower() == "true"
)


def validate_system_consistency(*, snapshot: dict, endpoint_name: str, response_fields: dict) -> bool:
    """Regression guard (regression-guard round; source-of-truth-upgrade
    round) — /product/summary is the only official decision source (its
    own endpoint, routers/product.py); `expected` below is reconstructed
    from that exact same authoritative value set, not a second, separate
    opinion. This works with zero new request/queries specifically
    because GET /product/summary and _compute_operations_snapshot()
    (above) run the identical pipeline on the identical inputs
    (rank_leads_by_priority() -> fetch_failure_pattern_rows() ->
    compute_failure_patterns() -> apply_failure_corrections() -> ...,
    live-console-consistency round's own fix) — so `snapshot` already
    holds product_summary's own main_action/execution_blocked/
    next_action/biggest_opportunity values verbatim, without calling that
    endpoint or its queries a second time. Compares those against
    whatever an endpoint's own response actually resolved to, catching
    the case where a *different* future edit desyncs an endpoint's
    response from the values product_summary would report for the same
    data. Pure in-memory dict comparison, no query, no re-scoring.

    Only runs when _VALIDATE_CONSISTENCY is on (off by default — see
    that flag's own comment). Never raises: a regression here should be
    visible (a warning log line, and consistency_warning=True on the
    caller's own response) rather than fatal to a real user's request."""
    if not _VALIDATE_CONSISTENCY:
        return True

    expected = {
        "main_action": snapshot.get("main_action"),
        "execution_blocked": snapshot.get("execution_blocked"),
        "next_best_action": snapshot.get("next_action"),
        "top_priority_lead_id": (
            snapshot["biggest_opportunity"]["lead_id"] if snapshot.get("biggest_opportunity") else None
        ),
    }
    mismatches = {
        field: {"expected": expected_value, "actual": response_fields.get(field)}
        for field, expected_value in expected.items()
        if field in response_fields and response_fields[field] != expected_value
    }
    if mismatches:
        logger.warning(
            "system_consistency_regression endpoint=%s mismatches=%s", endpoint_name, mismatches
        )
        return False
    return True


def _require_organization(session: dict) -> str:
    organization_id = session.get("organization_id")
    if organization_id is None:
        raise HTTPException(status_code=403, detail="Your account isn't part of an organization")
    return organization_id


async def _compute_operations_snapshot(db: AsyncSession, organization_id: str) -> dict:
    """Shared pipeline behind /system/day-plan, /system/sales-view,
    /system/console, /system/execution-lock, /system/execute-and-refresh,
    /system/command-center, and /system/narrative — the same sequence of
    already-existing service calls GET /product/summary (routers/
    product.py) itself makes (rank_leads_by_priority(),
    sum_today_potential_revenue(), compute_revenue_at_risk(),
    compute_daily_target_revenue(), compute_global_decision(),
    compute_revenue_gap(), compute_required_actions(),
    compute_response_metrics(), detect_revenue_leaks(),
    compute_sales_readiness(), simplify_system_state(),
    compute_main_action(), compute_decision_score(),
    compute_pressure_message()) — independently orchestrated here rather
    than importing that endpoint's own body, the same "each endpoint
    composes its own calls to shared services" pattern this codebase
    already follows for any two endpoints reading the same rank_leads_by_
    priority() pool (e.g. GET /intelligence/aggression-level and
    .../global-strategy each pay for their own call rather than sharing
    one). No new calculation anywhere in this function — every new
    caller added since this helper was first written only reads keys
    already computed here, or (decision_score/pressure_message) computed
    from local variables that already existed for another field's sake.

    Skips product_mode/kpis/efficiency entirely (ideal_actions_per_day
    floor passed as 0 to compute_required_actions — no floor override)
    since none of this snapshot's own callers need those dimensions, only
    the revenue/action-count/readiness figures product.py's own signals
    dict also carries. One extra query beyond the original day-plan/sales-
    view scope (compute_response_metrics()) was added when /system/console
    started needing sales_readiness_score/system_state too — the same
    already-established aggregate GET /intelligence/global-strategy
    already reuses; decision_score/pressure_message added no further query
    (both pure functions over figures already in scope).

    Live-console-consistency round: GET /product/summary applies compute_
    failure_patterns()/apply_failure_corrections() to `ranked` before
    anything else reads it (score/urgency corrections that can change
    which lead is mandatory, and therefore main_action/next_action/
    execution_blocked) — this function did not, so every /system/*
    endpoint built on it could disagree with /product/summary in the
    narrow case where a real failure pattern flips the mandatory pick.
    Fixed by running the exact same pass here, in the exact same order,
    reusing the exact same functions (compute_failure_patterns(),
    apply_failure_corrections() — neither reimplemented). The one
    unavoidable cost: fetch_failure_pattern_rows()'s own bounded query
    (moved to workday_engine.py from routers/product.py so both routers
    can call it without one importing from the other) — compute_
    conversion_insights()'s own two queries are deliberately skipped
    here, since apply_failure_corrections() never reads top_loss_reason
    (only worst_channel/failure_timing), so paying for that data a second
    time would buy nothing; top_loss_reason is passed as None instead."""
    now = datetime.now(timezone.utc)
    ranked = await rank_leads_by_priority(db, organization_id)

    failure_pattern_cutoff = now - timedelta(days=FAILURE_PATTERN_WINDOW_DAYS)
    failure_pattern_rows = await fetch_failure_pattern_rows(
        db, organization_id, cutoff=failure_pattern_cutoff
    )
    failure_patterns = compute_failure_patterns(
        ranked, {"top_loss_reason": None, "rows": failure_pattern_rows}
    )
    ranked = [apply_failure_corrections(lead, failure_patterns) for lead in ranked]

    open_leads = [lead for lead in ranked if lead.status not in ("converted", "lost")]

    revenue_today_expected = sum_today_potential_revenue(ranked, now=now)
    at_risk_cutoff = now - timedelta(days=AT_RISK_STALE_AFTER_DAYS)
    revenue_at_risk = compute_revenue_at_risk(ranked, now=now, stale_cutoff=at_risk_cutoff)

    revenue_cutoff = now - timedelta(days=DAILY_TARGET_REVENUE_WINDOW_DAYS)
    daily_target_revenue = await compute_daily_target_revenue(db, organization_id, revenue_cutoff)

    queue = build_action_queue(ranked)
    mandatory_lead = get_next_mandatory_lead(queue)
    required_action = reason = None
    if mandatory_lead is not None:
        required_action, reason = derive_required_action_and_reason(mandatory_lead)

    lost_opportunity_today = compute_lost_opportunity_today(ranked)
    simulation = simulate_revenue_if_all_actions_executed(ranked)
    aggression_level = compute_aggression_level(
        lost_opportunity_today=lost_opportunity_today,
        current_expected=simulation["current_expected"],
        delta=simulation["delta"],
    )

    decision = compute_global_decision(
        mandatory_lead=mandatory_lead,
        required_action=required_action,
        reason=reason,
        aggression_level=aggression_level,
    )

    revenue_gap = compute_revenue_gap(
        {"revenue_today_possible": revenue_today_expected},
        {"daily_target_revenue": daily_target_revenue},
    )
    required_actions = compute_required_actions(
        {
            "current_expected": simulation["current_expected"],
            "total_open_leads": len(open_leads),
            "next_action": decision["next_action"],
        },
        {"revenue_gap": revenue_gap},
        {"ideal_actions_per_day": 0},
    )

    biggest = max(open_leads, key=lambda lead: lead.expected_value, default=None)
    biggest_opportunity = (
        {
            "lead_id": biggest.id,
            "expected_value": biggest.expected_value,
            "next_best_action_type": biggest.next_best_action_type,
        }
        if biggest is not None
        else None
    )

    response_metrics = await compute_response_metrics(db, organization_id)
    leaks = detect_revenue_leaks(ranked)
    optimized_expected = simulation["optimized_expected"]
    execution_rate = (
        (simulation["current_expected"] / optimized_expected * 100) if optimized_expected > 0 else 100.0
    )
    overdue_count = sum(1 for lead in open_leads if lead.is_overdue)
    total_open_leads = len(open_leads)
    sales_readiness_score = compute_sales_readiness(
        {
            "daily_target_revenue": daily_target_revenue,
            "current_expected": simulation["current_expected"],
            "response_rate": response_metrics.response_rate,
            "execution_rate": execution_rate,
            "total_open_leads": total_open_leads,
            "overdue_count": overdue_count,
        },
        performance=None,
        leaks=leaks,
    )
    system_state = simplify_system_state({"sales_readiness_score": sales_readiness_score})
    main_action = compute_main_action(ranked)

    # decision_score/pressure_message (Task 4, live-console-finalization
    # round) — compute_decision_score()/compute_pressure_message() are
    # both already-existing intelligence.py functions (product.py already
    # calls them); reused verbatim here, not reimplemented.
    decision_score = compute_decision_score(
        {
            "total_open_leads": total_open_leads,
            "overdue_count": overdue_count,
            "daily_target_revenue": daily_target_revenue,
            "revenue_gap": revenue_gap,
            "current_expected": simulation["current_expected"],
        }
    )
    pressure_message = compute_pressure_message(
        {
            "revenue_gap": revenue_gap,
            "system_state": system_state,
            "main_action": main_action,
        }
    )

    return {
        "ranked": ranked,
        "open_leads": open_leads,
        "revenue_today_expected": revenue_today_expected,
        "revenue_at_risk": revenue_at_risk,
        "revenue_gap": revenue_gap,
        "next_action": decision["next_action"],
        "execution_blocked": decision["execution_blocked"],
        "required_actions_today": required_actions["required_actions_today"],
        "required_calls_today": required_actions["required_calls_today"],
        "required_messages_today": required_actions["required_messages_today"],
        "biggest_opportunity": biggest_opportunity,
        "sales_readiness_score": sales_readiness_score,
        "system_state": system_state,
        "main_action": main_action,
        "overdue_count": overdue_count,
        "total_open_leads": total_open_leads,
        "decision_score": decision_score,
        "pressure_message": pressure_message,
    }


class SystemEntryResponse(BaseModel):
    status: str
    recommended_access: str
    frontend_url: str
    api_docs_url: str
    message: str


@router.get("/entry", response_model=ApiResponse[SystemEntryResponse])
async def system_entry(
    request_id: str = Depends(get_request_id),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[SystemEntryResponse]:
    """Public, unauthenticated liveness check for "can the product actually
    be used right now" — deliberately a real DB round-trip (unlike GET
    /health, which only checks component presence, never calls out to
    anything), since a DB that can't be reached is exactly the condition
    that would also break GET /product/summary for every organization.
    No org/session context needed or assumed, unlike /product/summary
    itself, which is why this checks DB reachability as the closest
    session-free proxy rather than calling that endpoint's own logic."""
    start = time.perf_counter()

    try:
        await db.execute(text("SELECT 1"))
        status_value = "online"
        recommended_access = "frontend"
        message = "System is fully operational. Use the frontend for the normal experience."
    except Exception:
        status_value = "degraded"
        recommended_access = "api"
        message = (
            "Database is unreachable — frontend and API data endpoints will fail. "
            "Retry shortly or check backend logs."
        )

    return ApiResponse(
        success=True,
        data=SystemEntryResponse(
            status=status_value,
            recommended_access=recommended_access,
            frontend_url=FRONTEND_URL,
            api_docs_url=f"{settings.API_V1_PREFIX}/docs",
            message=message,
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


class SystemFirstAccessResponse(BaseModel):
    message: str
    steps: list[str]
    quick_start: dict[str, str]


@router.get("/first-access", response_model=ApiResponse[SystemFirstAccessResponse])
async def system_first_access(
    request_id: str = Depends(get_request_id),
) -> ApiResponse[SystemFirstAccessResponse]:
    """Onboarding copy, public and unauthenticated — no signal to aggregate,
    just fixed instructions pointing at endpoints that already exist
    (/system/demo-seed, /product/summary, /system/execute-action)."""
    start = time.perf_counter()

    return ApiResponse(
        success=True,
        data=SystemFirstAccessResponse(
            message=(
                "Bem-vindo ao Nexara. Este sistema prioriza automaticamente "
                "suas oportunidades de receita e diz exatamente o que fazer "
                "agora."
            ),
            steps=[
                "1. Crie ou carregue seus leads",
                "2. Acesse o resumo em /product/summary",
                "3. Execute a ação recomendada",
                "4. Atualize o lead e observe o sistema aprender",
            ],
            quick_start={
                "demo": f"{settings.API_V1_PREFIX}/system/demo-seed",
                "summary": f"{settings.API_V1_PREFIX}/product/summary",
                "execute": f"{settings.API_V1_PREFIX}/system/execute-action",
            },
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


class SystemExplainResponse(BaseModel):
    what_this_is: str
    how_it_works: list[str]
    what_you_gain: list[str]


@router.get("/explain", response_model=ApiResponse[SystemExplainResponse])
async def system_explain(
    request_id: str = Depends(get_request_id),
) -> ApiResponse[SystemExplainResponse]:
    """Sales/positioning copy, public and unauthenticated — fixed text, no
    per-tenant signal (a pitch describes the product category, not any one
    organization's own data)."""
    start = time.perf_counter()

    return ApiResponse(
        success=True,
        data=SystemExplainResponse(
            what_this_is=(
                "Um sistema que analisa seus leads e mostra exatamente onde "
                "está o dinheiro e o que fazer agora."
            ),
            how_it_works=[
                "Analisa comportamento dos leads",
                "Identifica oportunidades com maior chance de fechamento",
                "Prioriza automaticamente",
                "Define a ação exata para maximizar receita",
            ],
            what_you_gain=[
                "Mais vendas com menos esforço",
                "Zero desperdício de lead",
                "Decisão guiada por dados",
                "Execução clara e imediata",
            ],
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


class SystemExecuteActionRequest(BaseModel):
    lead_id: uuid.UUID


class SystemExecuteActionResponse(BaseModel):
    executed: bool
    action: str | None
    message_generated: str | None
    expected_revenue_impact: int


@router.post("/execute-action", response_model=ApiResponse[SystemExecuteActionResponse])
async def system_execute_action(
    body: SystemExecuteActionRequest,
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[SystemExecuteActionResponse]:
    """Manually-triggered equivalent of auto_execute_engine()'s own per-lead
    decision (execution_engine.py) — reuses the exact same scoring
    (score_leads()) and mutation (execute_lead_action()) that pipeline and
    POST /leads/{id}/execute-action already call; the only new code here is
    "read next_best_action_type off the already-scored lead and execute
    that, instead of requiring the caller to name an action" — no scoring
    or execution logic is reimplemented. executed=false (not an error) when
    the system's own recommendation is None/"monitor" — there is nothing
    to execute, same as auto_execute_engine()'s own skip condition for such
    leads."""
    start = time.perf_counter()
    organization_id = _require_organization(session)
    user_email = session.get("email")

    lead = await db.get(Lead, body.lead_id)
    if lead is None or lead.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Lead not found")

    (scored,) = await score_leads(db, [lead])
    action_type = scored.next_best_action_type

    if action_type is None or action_type == "monitor":
        return ApiResponse(
            success=True,
            data=SystemExecuteActionResponse(
                executed=False,
                action=action_type,
                message_generated=None,
                expected_revenue_impact=0,
            ),
            request_id=request_id,
            execution_time=time.perf_counter() - start,
        )

    try:
        await execute_lead_action(
            db,
            lead,
            action_type,
            response=scored,
            organization_id=organization_id,
            user_email=user_email,
        )
    except InvalidLeadAction as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await db.commit()

    return ApiResponse(
        success=True,
        data=SystemExecuteActionResponse(
            executed=True,
            action=action_type,
            message_generated=scored.ready_to_send_message,
            expected_revenue_impact=scored.expected_value,
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


class GuidedExecutionItem(BaseModel):
    lead_id: uuid.UUID
    company: str
    value: int
    action: str | None
    reason: str | None
    urgency: str


def _build_guided_execution_items(leads: list) -> list[GuidedExecutionItem]:
    """Shared by GET /system/guided-execution and GET /system/console —
    every field read straight off the already-scored LeadResponse, see
    GET /system/guided-execution's own docstring for which one each maps
    to. Pure formatting, no new computation; `leads` is whatever slice
    (already top-N) the caller passes in."""
    return [
        GuidedExecutionItem(
            lead_id=lead.id,
            company=lead.company_name or lead.name,
            value=lead.expected_value,
            action=lead.next_best_action,
            reason=lead.priority_reason,
            urgency=lead.next_best_action_urgency or "low",
        )
        for lead in leads
    ]


@router.get("/guided-execution", response_model=ApiResponse[list[GuidedExecutionItem]])
async def system_guided_execution(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[GuidedExecutionItem]]:
    """Guided Execution Mode (Task 2) — the top 5 of whatever rank_leads_
    by_priority() already prioritized (scoring.py; that pool IS the
    priority ordering, so "top 5" is simply its own first 5 entries, no
    new ranking). Every field read straight off the already-scored
    LeadResponse: company (company_name, falling back to name pre-
    enrichment), value (expected_value), action (next_best_action, the
    same full-sentence recommendation GET /leads already exposes), reason
    (priority_reason), urgency (next_best_action_urgency, "low" when the
    lead has no action at all — nothing urgent about it)."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    ranked = await rank_leads_by_priority(db, organization_id)
    open_leads = [lead for lead in ranked if lead.status not in ("converted", "lost")]

    return ApiResponse(
        success=True,
        data=_build_guided_execution_items(open_leads[:5]),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


class SystemDayPlanResponse(BaseModel):
    total_revenue_possible: int
    revenue_gap: float
    required_actions: int
    focus: str
    plan: list[str]


def _build_focus_and_plan(snapshot: dict) -> tuple[str, list[str]]:
    """Shared by GET /system/day-plan and GET /system/console — see GET
    /system/day-plan's own docstring for exactly which already-computed
    figure each `plan` line renders. Pure formatting/aggregation over
    `snapshot` (_compute_operations_snapshot()'s own dict, above), no new
    computation."""
    focus = FOCUS_BY_NEXT_ACTION.get(snapshot["next_action"], "messages")

    plan: list[str] = []
    if snapshot["required_calls_today"] > 0:
        plan.append(f"Ligue para {snapshot['required_calls_today']} leads hoje")
    if snapshot["required_messages_today"] > 0:
        plan.append(f"Envie mensagem para {snapshot['required_messages_today']} leads hoje")
    meetings_due = sum(
        1 for lead in snapshot["open_leads"] if lead.next_best_action_type == "schedule_meeting"
    )
    if meetings_due > 0:
        plan.append(f"Agende {meetings_due} reuniões")
    if not plan:
        plan.append("Nenhuma ação obrigatória agora — continue monitorando o pipeline")

    return focus, plan


@router.get("/day-plan", response_model=ApiResponse[SystemDayPlanResponse])
async def system_day_plan(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[SystemDayPlanResponse]:
    """One Click Day Plan (Task 3) — entirely derived from
    _compute_operations_snapshot()'s own already-computed figures (above),
    the same ones GET /product/summary exposes under different field
    names. focus/plan come from _build_focus_and_plan() (above) — never a
    fabricated number."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    snapshot = await _compute_operations_snapshot(db, organization_id)
    focus, plan = _build_focus_and_plan(snapshot)

    return ApiResponse(
        success=True,
        data=SystemDayPlanResponse(
            total_revenue_possible=snapshot["revenue_today_expected"],
            revenue_gap=snapshot["revenue_gap"],
            required_actions=snapshot["required_actions_today"],
            focus=focus,
            plan=plan,
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


class TopLead(BaseModel):
    id: uuid.UUID
    value: int
    action: str


class SystemSalesViewResponse(BaseModel):
    money_now: int
    money_at_risk: int
    next_action: str
    top_lead: TopLead | None


@router.get("/sales-view", response_model=ApiResponse[SystemSalesViewResponse])
async def system_sales_view(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[SystemSalesViewResponse]:
    """Minimal Sales Dashboard / "pitch view" (Task 6) — the same
    _compute_operations_snapshot() (above) day-plan uses, trimmed to the
    four numbers a demo actually leads with. top_lead is that snapshot's
    own biggest_opportunity (highest expected_value among open leads),
    same pick GET /product/summary's own biggest_opportunity makes."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    snapshot = await _compute_operations_snapshot(db, organization_id)

    top_lead = None
    biggest = snapshot["biggest_opportunity"]
    if biggest is not None:
        top_lead = TopLead(
            id=biggest["lead_id"],
            value=biggest["expected_value"],
            action=biggest["next_best_action_type"] or "monitor",
        )

    return ApiResponse(
        success=True,
        data=SystemSalesViewResponse(
            money_now=snapshot["revenue_today_expected"],
            money_at_risk=snapshot["revenue_at_risk"],
            next_action=snapshot["next_action"],
            top_lead=top_lead,
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


class ConsoleMoney(BaseModel):
    today_possible: int
    gap: float
    at_risk: int


class ConsoleTopPriority(BaseModel):
    lead_id: uuid.UUID
    name: str
    value: int
    action: str | None
    urgency: str
    reason: str | None


class SystemConsoleResponse(BaseModel):
    status: str
    message: str
    money: ConsoleMoney
    focus: str
    main_action: str
    required_actions: int
    execution_blocked: bool
    top_priorities: list[ConsoleTopPriority]
    execution_plan: list[str]
    next_steps: list[str]
    consistency_warning: bool = False


_CONSOLE_NEXT_STEPS = [
    "Execute a ação principal listada acima",
    "Atualize o status do lead logo após cada contato",
    "Recarregue o console para ver o sistema se ajustar",
]


@router.get("/console", response_model=ApiResponse[SystemConsoleResponse])
async def system_console(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[SystemConsoleResponse]:
    """Nexara Live Console (Task 1) — the one call GET /system/console-view
    itself makes. Zero new computation: one _compute_operations_snapshot()
    call (above — the same pipeline day-plan/sales-view already share)
    supplies everything here. status/message are simplify_system_state()'s
    own output (intelligence.py, keyed on sales_readiness_score);
    main_action is compute_main_action()'s own sentence (intelligence.py);
    focus/execution_plan are _build_focus_and_plan()'s own output (above,
    shared with GET /system/day-plan); top_priorities are _build_
    guided_execution_items()'s own output (above, shared with GET
    /system/guided-execution) reshaped with `name` instead of `company`
    for this view specifically — same LeadResponse fields, no new ones.
    next_steps is fixed onboarding-style copy, same spirit as GET
    /system/first-access's own `steps` — no per-tenant signal to derive
    it from."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    snapshot = await _compute_operations_snapshot(db, organization_id)
    focus, execution_plan = _build_focus_and_plan(snapshot)

    top_priorities = [
        ConsoleTopPriority(
            lead_id=lead.id,
            name=lead.name,
            value=lead.expected_value,
            action=lead.next_best_action,
            urgency=lead.next_best_action_urgency or "low",
            reason=lead.priority_reason,
        )
        for lead in snapshot["open_leads"][:5]
    ]

    consistent = validate_system_consistency(
        snapshot=snapshot,
        endpoint_name="console",
        response_fields={
            "main_action": snapshot["main_action"],
            "execution_blocked": snapshot["execution_blocked"],
            "top_priority_lead_id": top_priorities[0].lead_id if top_priorities else None,
        },
    )

    return ApiResponse(
        success=True,
        data=SystemConsoleResponse(
            status=snapshot["system_state"]["status"],
            message=snapshot["system_state"]["message"],
            money=ConsoleMoney(
                today_possible=snapshot["revenue_today_expected"],
                gap=snapshot["revenue_gap"],
                at_risk=snapshot["revenue_at_risk"],
            ),
            focus=focus,
            main_action=snapshot["main_action"],
            required_actions=snapshot["required_actions_today"],
            execution_blocked=snapshot["execution_blocked"],
            top_priorities=top_priorities,
            execution_plan=execution_plan,
            next_steps=_CONSOLE_NEXT_STEPS,
            consistency_warning=not consistent,
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


class SystemExecutionLockResponse(BaseModel):
    locked: bool
    reason: str
    required_action: str
    cta: str
    consistency_warning: bool = False


@router.get("/execution-lock", response_model=ApiResponse[SystemExecutionLockResponse])
async def system_execution_lock(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[SystemExecutionLockResponse]:
    """Execution Lock (Task 1, live-console-finalization round) — pure
    composition over _compute_operations_snapshot() (above): locked is
    that snapshot's own execution_blocked (compute_global_decision(),
    intelligence.py); required_action is its own main_action
    (compute_main_action()); reason is a plain-language rendering of two
    already-computed numbers (overdue_count, revenue_at_risk), no new
    calculation. cta is fixed copy — there's only one action this screen
    can offer either way."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    snapshot = await _compute_operations_snapshot(db, organization_id)

    if snapshot["execution_blocked"]:
        reason = (
            f"Você tem {snapshot['overdue_count']} leads atrasados com "
            f"R$ {format_brl(snapshot['revenue_at_risk'])} em risco"
        )
        cta = "Executar agora"
    else:
        reason = "Nenhum bloqueio ativo — pipeline sob controle"
        cta = "Continuar monitorando"

    consistent = validate_system_consistency(
        snapshot=snapshot,
        endpoint_name="execution-lock",
        response_fields={
            "execution_blocked": snapshot["execution_blocked"],
            "main_action": snapshot["main_action"],
        },
    )

    return ApiResponse(
        success=True,
        data=SystemExecutionLockResponse(
            locked=snapshot["execution_blocked"],
            reason=reason,
            required_action=snapshot["main_action"],
            cta=cta,
            consistency_warning=not consistent,
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


class SystemExecuteAndRefreshRequest(BaseModel):
    lead_id: uuid.UUID
    action: str


class SystemExecuteAndRefreshResponse(BaseModel):
    message: str
    expected_impact: str
    updated_summary: dict


@router.post("/execute-and-refresh", response_model=ApiResponse[SystemExecuteAndRefreshResponse])
async def system_execute_and_refresh(
    body: SystemExecuteAndRefreshRequest,
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[SystemExecuteAndRefreshResponse]:
    """Execute and Refresh (Task 2, live-console-finalization round) — a
    SIMULATION: reads and scores the lead (score_leads(), scoring.py — a
    pure computation, writes nothing) but never calls execute_lead_action()
    and never commits, so nothing is persisted. expected_impact is the
    lead's own already-computed expected_value (scoring.py), not a new
    projection. updated_summary is the current _compute_operations_
    snapshot() (above), trimmed to its JSON-serializable scalar fields —
    since nothing was persisted, this is the real current state, not a
    fabricated "what if" delta."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    lead = await db.get(Lead, body.lead_id)
    if lead is None or lead.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Lead not found")

    (scored,) = await score_leads(db, [lead])

    snapshot = await _compute_operations_snapshot(db, organization_id)
    updated_summary = {
        "revenue_today_expected": snapshot["revenue_today_expected"],
        "revenue_at_risk": snapshot["revenue_at_risk"],
        "revenue_gap": snapshot["revenue_gap"],
        "next_action": snapshot["next_action"],
        "execution_blocked": snapshot["execution_blocked"],
        "required_actions_today": snapshot["required_actions_today"],
        "sales_readiness_score": snapshot["sales_readiness_score"],
        "system_state": snapshot["system_state"],
        "main_action": snapshot["main_action"],
    }

    return ApiResponse(
        success=True,
        data=SystemExecuteAndRefreshResponse(
            message=f"Ação {body.action} simulada para {scored.name} — nada foi salvo.",
            expected_impact=f"+R$ {format_brl(scored.expected_value)} potencial",
            updated_summary=updated_summary,
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


class SystemCommandCenterResponse(BaseModel):
    status: str
    money_now: int
    money_lost: float
    main_action: str
    next_step: str
    leads_to_act: int
    consistency_warning: bool = False


@router.get("/command-center", response_model=ApiResponse[SystemCommandCenterResponse])
async def system_command_center(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[SystemCommandCenterResponse]:
    """Command Center, simplified view (Task 3, live-console-finalization
    round) — every field read straight off _compute_operations_snapshot()
    (above) or _build_focus_and_plan() (above, shared with GET /system/
    day-plan): money_lost is revenue_gap (the real, present shortfall —
    distinct from revenue_at_risk, which is pipeline-future risk);
    next_step is the day plan's own first line (the single most concrete
    already-computed action, distinct from main_action's one-sentence
    framing); leads_to_act is required_actions_today. No new calculation."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    snapshot = await _compute_operations_snapshot(db, organization_id)
    _focus, plan = _build_focus_and_plan(snapshot)

    consistent = validate_system_consistency(
        snapshot=snapshot,
        endpoint_name="command-center",
        response_fields={"main_action": snapshot["main_action"]},
    )

    return ApiResponse(
        success=True,
        data=SystemCommandCenterResponse(
            status=snapshot["system_state"]["status"],
            money_now=snapshot["revenue_today_expected"],
            money_lost=snapshot["revenue_gap"],
            main_action=snapshot["main_action"],
            next_step=plan[0],
            leads_to_act=snapshot["required_actions_today"],
            consistency_warning=not consistent,
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


class SystemNarrativeResponse(BaseModel):
    diagnosis: str
    opportunity: str
    action: str
    urgency: str


@router.get("/narrative", response_model=ApiResponse[SystemNarrativeResponse])
async def system_narrative(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[SystemNarrativeResponse]:
    """Auto Narrative (Task 4, live-console-finalization round) — pure
    composition over exactly the three signals named: diagnosis is
    pressure_message verbatim (compute_pressure_message(),
    intelligence.py — already a diagnosis-style sentence); opportunity is
    a plain-language rendering of revenue_gap (part of the same product-
    summary signal group); action is main_action verbatim; urgency is
    decision_score (compute_decision_score(), intelligence.py) reported
    as-is, not bucketed into a new label scheme — inventing thresholds to
    classify that number would be new logic this round's rules forbid."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    snapshot = await _compute_operations_snapshot(db, organization_id)

    return ApiResponse(
        success=True,
        data=SystemNarrativeResponse(
            diagnosis=snapshot["pressure_message"],
            opportunity=f"R$ {format_brl(snapshot['revenue_gap'])} recuperáveis hoje",
            action=snapshot["main_action"],
            urgency=f"{snapshot['decision_score']}/100",
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


class SystemDemoSeedResponse(BaseModel):
    created: int
    ready: bool
    auto_open: str
    expected_result: str


_DEMO_LEADS = [
    ("Carlos Mendes", "carlos.demo@techsolutions.com.br", "11999990001", "new"),
    ("Mariana Souza", "mariana.demo@retailplus.com.br", "11999990002", "contacted"),
    ("Roberto Alves", "roberto.demo@financecorp.com.br", "11999990003", "contacted"),
    ("Juliana Lima", "juliana.demo@healthgroup.com.br", "11999990004", "contacted"),
    ("Fernando Costa", "fernando.demo@manufaturabr.com.br", "11999990005", "lost"),
    ("Patricia Rocha", "patricia.demo@realestatepro.com.br", "11999990006", "contacted"),
    ("Ricardo Nunes", "ricardo.demo@hospitalitybr.com.br", "11999990007", "lost"),
    ("Camila Ferreira", "camila.demo@edutechbr.com.br", "11999990008", "new"),
    ("Lucas Martins", "lucas.demo@financeplus.com.br", "11999990009", "contacted"),
    ("Beatriz Cardoso", "beatriz.demo@techinova.com.br", "11999990010", "new"),
]
_DEMO_LOSS_REASONS = {"Fernando Costa": "Sem resposta", "Ricardo Nunes": "Preço alto"}
_DEMO_INTERESTED = {"Roberto Alves", "Juliana Lima"}
_DEMO_OVERDUE_DAYS = {"Juliana Lima": 2, "Lucas Martins": 3}


@router.post("/demo-seed", response_model=ApiResponse[SystemDemoSeedResponse])
async def system_demo_seed(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[SystemDemoSeedResponse]:
    """Sales-demo seed — the same lead/status/activity mix produced by hand
    (via POST /leads, .../enrich, PATCH .../status, .../record-response)
    earlier this project, now as one call. Reuses simulate_enrichment()
    (enrichment.py) for company_name/enrichment_data (estimated_value
    always lands in the 1k-20k range by construction — see that
    function's own docstring); status/loss-reason/interested-response
    writes mirror POST /leads' and PATCH /leads/{id}/status' own inline
    LeadActivityLog patterns (LOSS_REASON_MARKER, RESPONSE_EVENT_TYPE_BY_
    STATE — both scoring.py) rather than calling those endpoints' route
    functions directly, since those aren't extracted into standalone
    service functions and this round's rules forbid touching existing
    endpoints to extract one. Does not write LeadStatusHistory or fire
    automations — out of scope for a demo pool only /product/summary and
    GET /leads need to read."""
    start = time.perf_counter()
    organization_id = _require_organization(session)
    now = datetime.now(timezone.utc)

    created_leads: list[Lead] = []
    for name, email, phone, status in _DEMO_LEADS:
        lead = Lead(
            organization_id=organization_id,
            name=name,
            email=email,
            phone=phone,
            status="new",
            score=20,
        )
        db.add(lead)
        created_leads.append(lead)

    await db.flush()

    for lead, (name, _email, _phone, status) in zip(created_leads, _DEMO_LEADS):
        simulate_enrichment(lead)

        if status == "lost":
            reason = _DEMO_LOSS_REASONS.get(name, "Sem resposta")
            lead.status = "lost"
            db.add(
                LeadActivityLog(
                    organization_id=organization_id,
                    lead_id=lead.id,
                    lead_name=lead.name,
                    event_type="lead_lost",
                    message=f"Lead perdido. {LOSS_REASON_MARKER}{reason}",
                    # A fixed, plausible time-to-loss rather than reading
                    # lead.created_at — that column is server_default
                    # (populated by Postgres on flush, not guaranteed
                    # refreshed onto this Python object without an explicit
                    # refresh()), and these are demo leads created moments
                    # ago either way, so the exact figure isn't meaningful.
                    duration_seconds=3600,
                )
            )
        elif status == "contacted":
            lead.status = "contacted"
            if name in _DEMO_INTERESTED:
                db.add(
                    LeadActivityLog(
                        organization_id=organization_id,
                        lead_id=lead.id,
                        lead_name=lead.name,
                        event_type=RESPONSE_EVENT_TYPE_BY_STATE["interested"],
                        message="Lead demonstrou interesse.",
                    )
                )
            if name in _DEMO_OVERDUE_DAYS:
                lead.next_action = "Ligar para dar sequência"
                lead.next_action_due_at = now - timedelta(days=_DEMO_OVERDUE_DAYS[name])

    await db.commit()

    return ApiResponse(
        success=True,
        data=SystemDemoSeedResponse(
            created=len(created_leads),
            ready=True,
            auto_open=f"{settings.API_V1_PREFIX}/system/guided-execution",
            expected_result="Sistema pronto para demonstração imediata",
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


class AccessKitLogin(BaseModel):
    email: str
    password: str


class SystemAccessKitResponse(BaseModel):
    app_url: str
    api_url: str
    admin_lite_url: str
    login: AccessKitLogin
    how_to_use: list[str]


@router.get("/access-kit", response_model=ApiResponse[SystemAccessKitResponse])
async def system_access_kit(
    request_id: str = Depends(get_request_id),
) -> ApiResponse[SystemAccessKitResponse]:
    """Public, unauthenticated — just the fixed URLs/instructions a
    prospect or the founder needs to open the product, with no dependency
    on the frontend being up."""
    start = time.perf_counter()

    return ApiResponse(
        success=True,
        data=SystemAccessKitResponse(
            app_url=FRONTEND_URL,
            api_url=API_URL,
            admin_lite_url=f"{API_URL}{settings.API_V1_PREFIX}/system/admin-lite",
            login=AccessKitLogin(email="admin@elevel.com", password="12345678"),
            how_to_use=[
                "open admin_lite",
                "view summary",
                "execute actions",
                "update leads via API",
            ],
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


_ADMIN_LITE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Nexara — Admin Lite</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; background: #0b0b0f; color: #e4e4e7; }
  header { padding: 1rem 1.5rem; border-bottom: 1px solid #27272a; }
  main { padding: 1.5rem; max-width: 960px; margin: 0 auto; }
  .card { background: #18181b; border: 1px solid #27272a; border-radius: 0.5rem; padding: 1rem; margin-bottom: 1rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.75rem; }
  .stat-label { font-size: 0.75rem; color: #a1a1aa; text-transform: uppercase; }
  .stat-value { font-size: 1.5rem; font-weight: 600; margin-top: 0.25rem; }
  input { width: 100%; padding: 0.5rem; margin-bottom: 0.5rem; background: #27272a; border: 1px solid #3f3f46; border-radius: 0.375rem; color: #e4e4e7; box-sizing: border-box; }
  button { padding: 0.5rem 1rem; background: #6d28d9; border: none; border-radius: 0.375rem; color: white; cursor: pointer; font-size: 0.875rem; }
  button:hover { background: #5b21b6; }
  button:disabled { background: #3f3f46; cursor: not-allowed; }
  table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
  th, td { text-align: left; padding: 0.5rem; border-bottom: 1px solid #27272a; }
  #error { color: #f87171; font-size: 0.875rem; margin-top: 0.5rem; }
  #login-card { max-width: 360px; margin: 4rem auto; }
</style>
</head>
<body>
<header><strong>Nexara — Admin Lite</strong></header>
<main>
  <div id="login-card" class="card">
    <h3>Sign in</h3>
    <input id="email" type="email" placeholder="you@company.com" autocomplete="email" />
    <input id="password" type="password" placeholder="Password" autocomplete="current-password" />
    <button id="login-btn">Sign in</button>
    <div id="error"></div>
  </div>

  <div id="app" style="display:none">
    <div class="card">
      <div class="grid">
        <div><div class="stat-label">Revenue today</div><div class="stat-value" id="revenue-today">—</div></div>
        <div><div class="stat-label">Gap to target</div><div class="stat-value" id="revenue-gap">—</div></div>
        <div><div class="stat-label">System status</div><div class="stat-value" id="system-status">—</div></div>
      </div>
    </div>
    <div class="card">
      <div class="stat-label">Main action</div>
      <p id="main-action" style="margin: 0.5rem 0 0;">—</p>
    </div>
    <div class="card">
      <div class="stat-label" style="margin-bottom: 0.5rem;">Top leads</div>
      <table>
        <thead><tr><th>Name</th><th>Company</th><th>Status</th><th>Score</th><th></th></tr></thead>
        <tbody id="leads-body"></tbody>
      </table>
    </div>
  </div>
</main>

<script>
const API = "__API_PREFIX__";
let token = localStorage.getItem("nexara_admin_lite_token");

function showError(msg) {
  document.getElementById("error").textContent = msg || "";
}

async function api(path, options) {
  const res = await fetch(API + path, Object.assign({}, options, {
    headers: Object.assign({ "Content-Type": "application/json" }, token ? { "Authorization": "Bearer " + token } : {}, (options && options.headers) || {}),
  }));
  const body = await res.json();
  if (!res.ok || body.success === false) {
    throw new Error((body.errors && body.errors[0] && body.errors[0].message) || "Request failed");
  }
  return body.data;
}

async function loadDashboard() {
  document.getElementById("login-card").style.display = "none";
  document.getElementById("app").style.display = "block";

  const summary = await api("/product/summary");
  document.getElementById("revenue-today").textContent = "R$ " + Math.round(summary.revenue_today_possible).toLocaleString("pt-BR");
  document.getElementById("revenue-gap").textContent = "R$ " + Math.round(summary.revenue_gap).toLocaleString("pt-BR");
  document.getElementById("system-status").textContent = summary.system_status;
  document.getElementById("main-action").textContent = summary.main_action;

  const leads = await api("/leads");
  const list = (Array.isArray(leads) ? leads : leads.data || []).slice().sort((a, b) => b.score - a.score).slice(0, 5);
  const body = document.getElementById("leads-body");
  body.innerHTML = "";
  for (const lead of list) {
    const row = document.createElement("tr");
    row.innerHTML = "<td>" + lead.name + "</td><td>" + (lead.company_name || "—") + "</td><td>" + lead.status + "</td><td>" + lead.score + "</td><td></td>";
    const cell = row.lastElementChild;
    const btn = document.createElement("button");
    btn.textContent = "EXECUTE ACTION";
    btn.onclick = async () => {
      btn.disabled = true;
      try {
        const result = await api("/system/execute-action", { method: "POST", body: JSON.stringify({ lead_id: lead.id }) });
        alert(result.executed ? ("Executed: " + result.action) : "Nothing to execute for this lead right now.");
        loadDashboard();
      } catch (e) {
        alert(e.message);
        btn.disabled = false;
      }
    };
    cell.appendChild(btn);
    body.appendChild(row);
  }
}

document.getElementById("login-btn").addEventListener("click", async () => {
  showError("");
  try {
    const session = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: document.getElementById("email").value, password: document.getElementById("password").value }),
    });
    token = session.token;
    localStorage.setItem("nexara_admin_lite_token", token);
    await loadDashboard();
  } catch (e) {
    showError(e.message);
  }
});

if (token) {
  loadDashboard().catch(() => {
    localStorage.removeItem("nexara_admin_lite_token");
    token = null;
  });
}
</script>
</body>
</html>
"""


@router.get("/admin-lite", response_class=HTMLResponse, include_in_schema=False)
async def admin_lite() -> HTMLResponse:
    """Static, dependency-free HTML admin page served directly by the
    backend — same-origin fetches to the API below it, so it works
    whenever the API itself is up, independent of the Next.js frontend's
    own deployment status. No build step, no React, no new dependency.
    A plain .replace() (not %-formatting) fills in the API prefix — the
    page's own CSS/JS is full of literal `%`/`{`/`}` characters that would
    collide with either % or .format()-style templating."""
    return HTMLResponse(_ADMIN_LITE_HTML.replace("__API_PREFIX__", settings.API_V1_PREFIX))


_CONSOLE_VIEW_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Nexara — Revenue Command Center</title>
<style>
  :root { --bg: #000; --panel: #111111; --border: #262626; --text: #ffffff; --muted: #a3a3a3; --accent: #f97316; }
  * { box-sizing: border-box; }
  body { font-family: -apple-system, system-ui, sans-serif; margin: 0; background: var(--bg); color: var(--text); }
  header { padding: 2rem 2rem 1rem; }
  header h1 { margin: 0; font-size: 1.75rem; font-weight: 700; letter-spacing: -0.02em; }
  header .accent { color: var(--accent); }
  main { padding: 0 2rem 3rem; max-width: 1000px; margin: 0 auto; }
  .panel { background: var(--panel); border: 1px solid var(--border); border-radius: 1rem; padding: 1.5rem; margin-bottom: 1.5rem; }
  .money-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; }
  .money-label { font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
  .money-value { font-size: 2.25rem; font-weight: 700; margin-top: 0.35rem; }
  .money-value.risk { color: var(--accent); }
  .main-action-panel { text-align: center; padding: 3rem 1.5rem; }
  .main-action-label { font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
  .main-action-text { font-size: 2.5rem; font-weight: 800; margin: 1rem auto; max-width: 780px; line-height: 1.25; }
  .status-badge { display: inline-block; padding: 0.25rem 0.75rem; border-radius: 999px; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; margin-bottom: 0.5rem; }
  .status-on_track { background: #14532d; color: #86efac; }
  .status-attention { background: #713f12; color: #fde047; }
  .status-critical { background: #7f1d1d; color: #fca5a5; }
  .alert-block { background: #7f1d1d; border: 1px solid #b91c1c; border-radius: 1rem; padding: 1.25rem 1.5rem; margin-bottom: 1.5rem; font-weight: 700; font-size: 1.05rem; }
  .alert-block .tag { display: block; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #fca5a5; font-weight: 600; margin-bottom: 0.35rem; }
  .exec-btn { background: var(--accent); color: #000; border: none; border-radius: 0.75rem; padding: 1rem 2rem; font-size: 1rem; font-weight: 700; cursor: pointer; margin-top: 1rem; }
  .exec-btn:hover { background: #fb923c; }
  .exec-btn:disabled { background: #404040; color: #a3a3a3; cursor: not-allowed; }
  h2 { font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin: 0 0 1rem; }
  .leads-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1rem; }
  .lead-card { background: #1a1a1a; border: 1px solid var(--border); border-radius: 0.75rem; padding: 1rem; }
  .lead-card .name { font-weight: 700; font-size: 1.05rem; }
  .lead-card .value { color: var(--accent); font-weight: 700; margin: 0.25rem 0; }
  .lead-card .action { font-size: 0.85rem; color: var(--muted); margin-bottom: 0.5rem; }
  .urgency-tag { display: inline-block; font-size: 0.7rem; text-transform: uppercase; padding: 0.15rem 0.5rem; border-radius: 999px; }
  .urgency-high, .urgency-immediate { background: #7f1d1d; color: #fca5a5; }
  .urgency-medium { background: #713f12; color: #fde047; }
  .urgency-low { background: #262626; color: #a3a3a3; }
  ul.plan-list { margin: 0; padding-left: 1.25rem; }
  ul.plan-list li { margin-bottom: 0.5rem; }
  input { width: 100%; padding: 0.65rem; margin-bottom: 0.5rem; background: #1a1a1a; border: 1px solid var(--border); border-radius: 0.5rem; color: var(--text); }
  #login-card { max-width: 380px; margin: 6rem auto; }
  #login-card button { width: 100%; background: var(--accent); color: #000; border: none; border-radius: 0.5rem; padding: 0.75rem; font-weight: 700; cursor: pointer; }
  #error { color: #fca5a5; font-size: 0.85rem; margin-top: 0.5rem; }
</style>
</head>
<body>
<header>
  <h1>NEXARA <span class="accent">–</span> Revenue Command Center</h1>
</header>
<main>
  <div id="login-card" class="panel">
    <h2>Sign in</h2>
    <input id="email" type="email" placeholder="you@company.com" autocomplete="email" />
    <input id="password" type="password" placeholder="Password" autocomplete="current-password" />
    <button id="login-btn">Sign in</button>
    <div id="error"></div>
  </div>

  <div id="app" style="display:none">
    <div id="alert-block" class="alert-block" style="display:none">
      <span class="tag">Execução bloqueada</span>
      <span id="alert-text"></span>
    </div>

    <div class="panel">
      <div class="money-grid">
        <div><div class="money-label">Dinheiro hoje</div><div class="money-value" id="money-today">—</div></div>
        <div><div class="money-label">Dinheiro perdido</div><div class="money-value risk" id="money-gap">—</div></div>
      </div>
    </div>

    <div class="panel main-action-panel">
      <div class="status-badge" id="status-badge">—</div>
      <div class="main-action-label">Ação principal</div>
      <div class="main-action-text" id="main-action">—</div>
      <button class="exec-btn" id="exec-btn">EXECUTAR AÇÃO AGORA</button>
    </div>

    <div class="panel">
      <h2>Top 3 leads</h2>
      <div class="leads-grid" id="leads-grid"></div>
    </div>

    <div class="panel">
      <h2>Plano de execução</h2>
      <ul class="plan-list" id="plan-list"></ul>
    </div>
  </div>
</main>

<script>
const API = "__API_PREFIX__";
let token = localStorage.getItem("nexara_console_token");
let topLeadId = null;

function showError(msg) {
  document.getElementById("error").textContent = msg || "";
}

async function api(path, options) {
  const res = await fetch(API + path, Object.assign({}, options, {
    headers: Object.assign({ "Content-Type": "application/json" }, token ? { "Authorization": "Bearer " + token } : {}, (options && options.headers) || {}),
  }));
  const body = await res.json();
  if (!res.ok || body.success === false) {
    throw new Error((body.errors && body.errors[0] && body.errors[0].message) || "Request failed");
  }
  return body.data;
}

function money(value) {
  return "R$ " + Math.round(value).toLocaleString("pt-BR");
}

async function loadConsole() {
  document.getElementById("login-card").style.display = "none";
  document.getElementById("app").style.display = "block";

  const data = await api("/system/console");

  document.getElementById("money-today").textContent = money(data.money.today_possible);
  document.getElementById("money-gap").textContent = money(data.money.gap);

  const alertBlock = document.getElementById("alert-block");
  if (data.execution_blocked) {
    document.getElementById("alert-text").textContent = data.message;
    alertBlock.style.display = "block";
  } else {
    alertBlock.style.display = "none";
  }

  const badge = document.getElementById("status-badge");
  badge.textContent = data.status.replace("_", " ");
  badge.className = "status-badge status-" + data.status;

  document.getElementById("main-action").textContent = data.main_action;

  const grid = document.getElementById("leads-grid");
  grid.innerHTML = "";
  topLeadId = null;
  data.top_priorities.slice(0, 3).forEach((lead, index) => {
    if (index === 0) topLeadId = lead.lead_id;
    const card = document.createElement("div");
    card.className = "lead-card";
    card.innerHTML =
      "<div class=\\"name\\">" + lead.name + "</div>" +
      "<div class=\\"value\\">" + money(lead.value) + "</div>" +
      "<div class=\\"action\\">" + (lead.action || "—") + "</div>" +
      "<span class=\\"urgency-tag urgency-" + lead.urgency + "\\">" + lead.urgency + "</span>";
    grid.appendChild(card);
  });

  const planList = document.getElementById("plan-list");
  planList.innerHTML = "";
  data.execution_plan.forEach((line) => {
    const li = document.createElement("li");
    li.textContent = line;
    planList.appendChild(li);
  });

  const execBtn = document.getElementById("exec-btn");
  execBtn.disabled = !topLeadId;
}

document.getElementById("exec-btn").addEventListener("click", async () => {
  if (!topLeadId) return;
  const btn = document.getElementById("exec-btn");
  btn.disabled = true;
  const originalText = btn.textContent;
  btn.textContent = "Executando...";
  try {
    const result = await api("/system/execute-action", { method: "POST", body: JSON.stringify({ lead_id: topLeadId }) });
    alert(result.executed ? ("Executado: " + result.action) : "Nada para executar neste lead agora.");
    await loadConsole();
  } catch (e) {
    alert(e.message);
  } finally {
    btn.textContent = originalText;
    btn.disabled = !topLeadId;
  }
});

document.getElementById("login-btn").addEventListener("click", async () => {
  showError("");
  try {
    const session = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: document.getElementById("email").value, password: document.getElementById("password").value }),
    });
    token = session.token;
    localStorage.setItem("nexara_console_token", token);
    await loadConsole();
  } catch (e) {
    showError(e.message);
  }
});

if (token) {
  loadConsole().catch(() => {
    localStorage.removeItem("nexara_console_token");
    token = null;
  });
}
</script>
</body>
</html>
"""


@router.get("/console-view", response_class=HTMLResponse, include_in_schema=False)
async def console_view() -> HTMLResponse:
    """Nexara Live Console UI (product-layer round Task 2; enhanced Task 5,
    live-console-finalization round) — pure HTML/CSS/vanilla JS, no build
    step, no React, same dependency-free pattern as GET /system/
    admin-lite (which this reuses the login/token approach from). Fetches
    only GET /system/console (above), which is itself pure aggregation of
    already-existing signals — this page adds no computation of its own,
    only rendering: top money block trimmed to today_possible/gap, the
    alert block shown purely from execution_blocked/message (both already
    on the same response, no second fetch), lead cards sliced to 3
    client-side. "EXECUTAR AÇÃO AGORA" calls the existing POST
    /system/execute-action for whichever lead top_priorities[0] names."""
    return HTMLResponse(_CONSOLE_VIEW_HTML.replace("__API_PREFIX__", settings.API_V1_PREFIX))
