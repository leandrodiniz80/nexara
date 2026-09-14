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
from app.services.leads.enrichment import simulate_enrichment
from app.services.leads.execution_engine import InvalidLeadAction, execute_lead_action
from app.services.leads.intelligence import (
    FOCUS_BY_NEXT_ACTION,
    compute_global_decision,
    compute_required_actions,
    compute_revenue_gap,
)
from app.services.leads.scoring import (
    LOSS_REASON_MARKER,
    RESPONSE_EVENT_TYPE_BY_STATE,
    compute_aggression_level,
    rank_leads_by_priority,
    score_leads,
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

FRONTEND_URL = "https://invigorating-stillness-production-07d1.up.railway.app"
API_URL = "https://nexara-production-4254.up.railway.app"


def _require_organization(session: dict) -> str:
    organization_id = session.get("organization_id")
    if organization_id is None:
        raise HTTPException(status_code=403, detail="Your account isn't part of an organization")
    return organization_id


async def _compute_operations_snapshot(db: AsyncSession, organization_id: str) -> dict:
    """Shared pipeline behind /system/day-plan and /system/sales-view — the
    same sequence of already-existing service calls GET /product/summary
    (routers/product.py) itself makes (rank_leads_by_priority(),
    sum_today_potential_revenue(), compute_revenue_at_risk(),
    compute_daily_target_revenue(), compute_global_decision(),
    compute_revenue_gap(), compute_required_actions()) — independently
    orchestrated here rather than importing that endpoint's own body, the
    same "each endpoint composes its own calls to shared services" pattern
    this codebase already follows for any two endpoints reading the same
    rank_leads_by_priority() pool (e.g. GET /intelligence/aggression-level
    and .../global-strategy each pay for their own call rather than
    sharing one). No new calculation anywhere in this function.

    Skips product_mode/kpis entirely (ideal_actions_per_day floor passed
    as 0 to compute_required_actions — no floor override) since none of
    this snapshot's own callers need that dimension, only the revenue/
    action-count figures product.py's own signals dict also carries."""
    now = datetime.now(timezone.utc)
    ranked = await rank_leads_by_priority(db, organization_id)
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
    top_five = open_leads[:5]

    items = [
        GuidedExecutionItem(
            lead_id=lead.id,
            company=lead.company_name or lead.name,
            value=lead.expected_value,
            action=lead.next_best_action,
            reason=lead.priority_reason,
            urgency=lead.next_best_action_urgency or "low",
        )
        for lead in top_five
    ]

    return ApiResponse(
        success=True,
        data=items,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


class SystemDayPlanResponse(BaseModel):
    total_revenue_possible: int
    revenue_gap: float
    required_actions: int
    focus: str
    plan: list[str]


@router.get("/day-plan", response_model=ApiResponse[SystemDayPlanResponse])
async def system_day_plan(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[SystemDayPlanResponse]:
    """One Click Day Plan (Task 3) — entirely derived from
    _compute_operations_snapshot()'s own already-computed figures (above),
    the same ones GET /product/summary exposes under different field
    names. focus reuses FOCUS_BY_NEXT_ACTION (compute_required_actions()'s
    own next_action -> calls/messages/meetings mapping, intelligence.py)
    rather than a new channel classification. Each `plan` line is a plain-
    language rendering of a real already-computed count — required_calls_
    today/required_messages_today (compute_required_actions()) for the
    first two lines, and a count of open leads whose own next_best_
    action_type is already "schedule_meeting" (no new classification, just
    tallying an existing field across the same `ranked` pool) for the
    third — never a fabricated number."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    snapshot = await _compute_operations_snapshot(db, organization_id)
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
