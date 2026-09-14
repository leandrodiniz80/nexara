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
from app.services.leads.scoring import LOSS_REASON_MARKER, RESPONSE_EVENT_TYPE_BY_STATE, score_leads

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


class SystemDemoSeedResponse(BaseModel):
    created: int
    ready: bool


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
        data=SystemDemoSeedResponse(created=len(created_leads), ready=True),
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
