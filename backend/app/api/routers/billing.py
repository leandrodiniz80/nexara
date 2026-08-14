import time

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.dependencies.auth import get_current_session, get_platform_container
from app.api.dependencies.billing import (
    get_billing_analytics,
    get_billing_metrics,
    get_business_overview_engine,
    get_lead_execution_tracker,
    get_revenue_activation_engine,
    get_sales_playbook_engine,
    get_stripe_service,
    get_stripe_sync_service,
)
from app.api.dependencies.common import get_request_id
from app.api.dependencies.tenant import get_request_tenant_id
from app.api.dependencies.tenant_context_guard import ensure_tenant_access
from app.api.responses.api_response import ApiResponse
from app.core.config import settings
from app.platform.billing.billing_analytics import BillingAnalytics
from app.platform.billing.billing_metrics import BillingMetrics
from app.platform.billing.stripe_service import StripeService
from app.platform.billing.stripe_sync import StripeSyncService
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.revenue.business_overview import BusinessOverviewEngine
from app.platform.revenue.lead_execution import LeadExecutionTracker
from app.platform.revenue.revenue_activation import RevenueActivationEngine
from app.platform.revenue.sales_playbook import SalesPlaybookEngine

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/billing", tags=["Billing"])

# Sprint 269: each Stripe event type this router acts on gets its own,
# specific audit event name — not one generic "stripe_event" catch-all —
# matching this platform's established convention (organization_renamed,
# api_key_created, metrics_global_access, ...) of naming each audited
# action distinctly, so a future consumer (e.g. a revenue/churn
# dashboard) can filter by exactly what happened rather than re-parsing
# a generic bucket. "checkout.session.completed" keeps the original
# "plan_upgraded" name from Sprint 268, unchanged, for backward
# compatibility with anything already querying that event type.
_STRIPE_EVENT_AUDIT_NAMES = {
    "checkout.session.completed": "plan_upgraded",
    "invoice.payment_failed": "subscription_payment_failed",
    "customer.subscription.deleted": "subscription_canceled",
    "customer.subscription.updated": "subscription_updated",
}


class PlanResponse(BaseModel):
    plan: str
    limits: dict[str, int]


class UpgradeRequest(BaseModel):
    plan: str


class UpgradeResponse(BaseModel):
    checkout_url: str | None = None


@router.get("/plan", response_model=ApiResponse[PlanResponse])
async def get_plan(
    session: dict = Depends(get_current_session),
    request_id: str = Depends(get_request_id),
    container: PlatformContainer = Depends(get_platform_container),
    tenant_id: str | None = Depends(get_request_tenant_id),
) -> ApiResponse[PlanResponse]:
    start = time.perf_counter()

    if tenant_id is None:
        raise HTTPException(status_code=404, detail="No organization found")

    ensure_tenant_access(session, tenant_id)

    auth = container.auth()
    plan = auth.get_organization_plan(tenant_id)

    data = PlanResponse(plan=plan, limits=auth.get_plan_limits(plan))

    return ApiResponse(
        success=True,
        data=data,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.post("/upgrade", response_model=ApiResponse[UpgradeResponse])
async def upgrade_plan(
    body: UpgradeRequest,
    session: dict = Depends(get_current_session),
    request_id: str = Depends(get_request_id),
    container: PlatformContainer = Depends(get_platform_container),
    stripe_service: StripeService | None = Depends(get_stripe_service),
    tenant_id: str | None = Depends(get_request_tenant_id),
) -> ApiResponse[UpgradeResponse]:
    start = time.perf_counter()

    if tenant_id is None:
        raise HTTPException(status_code=404, detail="No organization found")

    ensure_tenant_access(session, tenant_id)

    auth = container.auth()
    org_role = auth.get_user_organization_role(session["email"])

    if org_role != "owner":
        raise HTTPException(
            status_code=403, detail="Only the organization owner can change the plan"
        )

    if stripe_service is not None:
        # Stripe configured: don't upgrade yet — hand back a checkout URL and let
        # the webhook apply the plan once Stripe confirms payment.
        try:
            checkout_url = stripe_service.create_checkout_session(tenant_id, body.plan)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        data = UpgradeResponse(checkout_url=checkout_url)
    else:
        # Manual fallback — the pre-Stripe flow, byte-for-byte: upgrade immediately.
        try:
            auth.set_organization_plan(tenant_id, body.plan)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        data = UpgradeResponse(checkout_url=None)

    return ApiResponse(
        success=True,
        data=data,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.post("/webhook", response_model=ApiResponse[dict])
async def stripe_webhook(
    request: Request,
    request_id: str = Depends(get_request_id),
    container: PlatformContainer = Depends(get_platform_container),
    stripe_service: StripeService | None = Depends(get_stripe_service),
) -> ApiResponse[dict]:
    """The single Stripe webhook endpoint (Sprint 268, extended in 269
    per explicit product decision — see stripe_service.py's own
    docstring — rather than a second, parallel checkout/webhook flow:
    Stripe can only be configured to call one URL, and a second endpoint
    capable of processing the same events would either sit dead or, if
    both were ever live, double-process every event — this class's
    idempotency guard only protects a single logical event stream).

    Signature validation happens unconditionally inside
    `handle_webhook()`, before any event data is trusted, for every
    event type — never skipped, never bypassed based on event type.
    Always acknowledges Stripe with 2xx once the signature itself is
    valid (`{"received": True}`), even when `result` is `None` (a
    duplicate delivery, an unhandled event type, or one this can't
    safely resolve an organization for) — Stripe retries on anything
    other than 2xx, and retrying an event this deliberately chose to
    ignore would just repeat the same no-op forever.
    """
    start = time.perf_counter()

    if stripe_service is None:
        raise HTTPException(status_code=503, detail="Stripe is not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        result = stripe_service.handle_webhook(payload, sig_header)
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(status_code=400, detail="Invalid signature") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid payload") from exc

    if result is not None:
        auth = container.auth()
        org_id = result.get("org_id")

        # Events after checkout (payment_failed, subscription updated/
        # deleted) carry a Stripe customer id, not the original checkout
        # metadata — resolved via the reverse index set up when the
        # customer/subscription ids were first persisted at checkout.
        if org_id is None and result.get("stripe_customer_id"):
            org_id = auth.find_organization_by_stripe_customer(result["stripe_customer_id"])

        if org_id is not None:
            if result["event_type"] == "checkout.session.completed":
                auth.set_stripe_ids(
                    org_id, result.get("stripe_customer_id"), result.get("stripe_subscription_id")
                )

            if "plan" in result:
                auth.set_organization_plan(org_id, result["plan"])

            if "subscription_status" in result:
                auth.set_subscription_status(org_id, result["subscription_status"])

            if container.audit is not None:
                container.audit.log_event(
                    _STRIPE_EVENT_AUDIT_NAMES.get(result["event_type"], "stripe_event_processed"),
                    None,
                    org_id,
                    {
                        "type": result["event_type"],
                        "plan": result.get("plan"),
                        "subscription_status": result.get("subscription_status"),
                        # Kept from Sprint 268's own original metadata
                        # shape ({"plan": ..., "source": "stripe"}) — no
                        # reason to drop a field a future consumer might
                        # already filter on, now that "type" carries the
                        # more specific detail "source" alone didn't.
                        "source": "stripe",
                    },
                )

    return ApiResponse(
        success=True,
        data={"received": True},
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


def _require_admin(session: dict, container: PlatformContainer) -> str:
    """Sprint 272. Same gate as cdn.py's own `_require_admin()` (Sprint
    257) — duplicated locally rather than imported cross-router, matching
    this codebase's existing convention of each router file owning its
    own small auth helpers (`_require_owner`/`_require_own_tenant_id` in
    tenants.py, `_require_admin` in cdn.py).

    The spec's own `/billing/dashboard` had no auth dependency at all —
    `mrr`/`arr`/`churn_rate`/etc. aggregate every organization on the
    platform, so an unauthenticated (or merely tenant-owner-authenticated)
    caller would see the whole company's revenue and every other tenant's
    plan/cancellation status. This is platform operational data, not
    tenant business data, so it uses the same global `role == "admin"`
    check as `/metrics/webhook/metrics` (cdn.py) and `/metrics/audit` —
    not `_require_owner()`, which only confirms ownership of the caller's
    *own* tenant and would still leak every other tenant's numbers.
    """
    role = container.auth().get_user_role(session["email"])

    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")

    return role


class BillingDashboardResponse(BaseModel):
    mrr: int
    arr: int
    active_customers: int
    total_customers: int
    churn_rate: float
    arpu: float
    ltv: float


_BILLING_DASHBOARD_AUDIT_EVENT = "billing_dashboard_access"


@router.get("/dashboard", response_model=ApiResponse[BillingDashboardResponse])
async def billing_dashboard(
    session: dict = Depends(get_current_session),
    request_id: str = Depends(get_request_id),
    container: PlatformContainer = Depends(get_platform_container),
    metrics: BillingMetrics = Depends(get_billing_metrics),
) -> ApiResponse[BillingDashboardResponse]:
    """SaaS-wide financial rollup (Sprint 272): MRR, ARR, active/total
    customers, churn rate, ARPU, LTV — all derived from `PlatformAuth`'s
    persisted plan/subscription state via `BillingMetrics`, no Stripe
    runtime calls and no separate billing store.

    Admin-only and audited (`billing_dashboard_access`) — see
    `_require_admin()`'s own docstring above for why this needed real
    authorization at all, unlike the spec's own version.
    """
    start = time.perf_counter()

    role = _require_admin(session, container)

    if container.audit is not None:
        organization_id = container.auth().get_user_organization(session["email"])
        container.audit.log_event(
            _BILLING_DASHBOARD_AUDIT_EVENT,
            session["email"],
            organization_id,
            {"role": role},
        )

    data = BillingDashboardResponse(**metrics.calculate())

    return ApiResponse(
        success=True,
        data=data,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


class BillingAnalyticsResponse(BaseModel):
    revenue_series: list[dict]
    growth_rate: float
    plan_distribution: dict[str, int]
    churn_series: list[dict]
    # Sprint 274 — current-state metrics, additive to Sprint 273's
    # historical/cohort ones above. `BillingAnalyticsResponse` is a
    # `BaseModel` with explicit fields only, so these had to be declared
    # here or FastAPI's `response_model` validation would silently strip
    # them from the response even though the endpoint computed them.
    mrr: int
    arr: int
    active_customers: int
    churn_rate: float
    ltv: float
    # Sprint 275 — revenue segmentation + expansion/contraction, same
    # "must be declared or response_model silently drops it" reasoning.
    revenue_by_plan: dict[str, int]
    expansion_revenue: int
    contraction_revenue: int
    net_revenue_change: int
    # Sprint 276 — forecast/health/anomalies, same reasoning as above.
    forecast: list[dict]
    health_score: dict
    anomalies: list[dict]
    # Sprint 277 — churn prediction / upgrade nudges / risk-adjusted LTV,
    # same reasoning as above.
    churn_prediction: list[dict]
    upgrade_recommendations: list[dict]
    predicted_ltv: float


_BILLING_ANALYTICS_AUDIT_EVENT = "billing_analytics_access"


@router.get("/analytics", response_model=ApiResponse[BillingAnalyticsResponse])
async def billing_analytics(
    session: dict = Depends(get_current_session),
    request_id: str = Depends(get_request_id),
    container: PlatformContainer = Depends(get_platform_container),
    analytics: BillingAnalytics = Depends(get_billing_analytics),
) -> ApiResponse[BillingAnalyticsResponse]:
    """Billing intelligence (Sprints 273-277, single endpoint per each
    sprint's own "keep endpoint único" rule): revenue-by-signup-month,
    MoM growth rate, plan distribution, churn-by-month (historical/
    cohort, Sprint 273), plus current-state MRR/ARR/active customers/
    churn rate/LTV (Sprint 274), plus revenue-by-plan segmentation and
    expansion/contraction/net revenue change (Sprint 275), plus a
    3-month revenue forecast, a per-organization health score, and
    month-over-month revenue anomaly flags (Sprint 276), plus per-org
    churn-risk classification, free-plan upgrade recommendations, and a
    churn-risk-adjusted LTV figure (Sprint 277) — all derived from
    `BillingAnalytics`, which as of this sprint also reads `alerts_sent`
    usage (via an injected `get_usage` callable, not a hard
    `LoaderMetricsStore` dependency — see `get_billing_analytics()`'s own
    docstring) alongside `PlatformAuth.list_organizations()`. No Stripe
    runtime, no separate store. Admin-only and audited
    (`billing_analytics_access`), same pattern as `/billing/dashboard`
    right above.

    Fixes from each sprint's own router code (Sprint 273's own version of
    this endpoint already fixed the `_require_admin(session)` /
    `{"data": data}` / audit-shape issues in its own spec — see the
    SWEEP FINAL for that sprint):

    1. Sprint 274: `return ApiResponse.success(data)` — `ApiResponse` has
       no `.success()` classmethod (see app/api/responses/api_response.py);
       only `from_service_result()` and the ordinary constructor exist,
       and `request_id`/`execution_time` are both required fields with
       no default. Would raise `AttributeError` on every call. Built via
       the same `ApiResponse(success=True, data=..., request_id=...,
       execution_time=...)` shape as every other endpoint in this file.
    2. Sprint 274 and 275 both: `BillingAnalyticsResponse` needed its new
       fields declared (see its own comments above) or `response_model`
       validation would silently drop them from the response.
    3. Sprint 275's real fix isn't in this endpoint at all — see
       `PlatformAuth.set_organization_plan()`'s own docstring for a
       spec that would have silently dropped an unrelated method's
       validation, error handling, and cache invalidation.
    """
    start = time.perf_counter()

    role = _require_admin(session, container)

    if container.audit is not None:
        organization_id = container.auth().get_user_organization(session["email"])
        container.audit.log_event(
            _BILLING_ANALYTICS_AUDIT_EVENT,
            session["email"],
            organization_id,
            {"role": role},
        )

    data = BillingAnalyticsResponse(
        revenue_series=analytics.revenue_timeseries(),
        growth_rate=analytics.growth_rate(),
        plan_distribution=analytics.plan_distribution(),
        churn_series=analytics.churn_over_time(),
        mrr=analytics.active_mrr(),
        arr=analytics.arr(),
        active_customers=analytics.active_customers(),
        churn_rate=analytics.churn_rate(),
        ltv=analytics.ltv(),
        revenue_by_plan=analytics.revenue_by_plan(),
        expansion_revenue=analytics.expansion_revenue(),
        contraction_revenue=analytics.contraction_revenue(),
        net_revenue_change=analytics.net_revenue_change(),
        forecast=analytics.forecast_mrr(),
        health_score=analytics.customer_health_score(),
        anomalies=analytics.detect_revenue_anomalies(),
        churn_prediction=analytics.predict_churn(),
        upgrade_recommendations=analytics.upgrade_recommendations(),
        predicted_ltv=analytics.predicted_ltv(),
    )

    return ApiResponse(
        success=True,
        data=data,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


class PortalSessionResponse(BaseModel):
    status: str
    url: str | None = None
    reason: str | None = None


@router.post("/portal", response_model=ApiResponse[PortalSessionResponse])
async def create_billing_portal(
    session: dict = Depends(get_current_session),
    request_id: str = Depends(get_request_id),
    container: PlatformContainer = Depends(get_platform_container),
    stripe_sync: StripeSyncService | None = Depends(get_stripe_sync_service),
    tenant_id: str | None = Depends(get_request_tenant_id),
) -> ApiResponse[PortalSessionResponse]:
    """Self-serve Stripe Customer Portal (Sprint 280) — the customer
    manages their own upgrade/downgrade/cancellation/payment method
    directly through Stripe's own hosted UI from here on; this endpoint
    only ever *starts* that flow (`StripeSyncService.create_portal_
    session()`), never changes `plan`/`subscription_status` itself —
    those still only change via the existing webhook, once Stripe
    confirms whatever the customer actually did. Owner-only, same gate
    `/upgrade` already applies right above: managing billing/payment
    method/cancellation is exactly the same class of sensitive, org-wide
    action.

    Fixes from the spec's own router code:

    1. `session: Session = Depends(require_auth)` — neither `Session`
       (as a type) nor `require_auth` exist anywhere in this codebase;
       every other endpoint in this file uses `session: dict =
       Depends(get_current_session)`.
    2. No owner check at all — as written, any authenticated member of
       an organization (not just its owner) could generate a live link
       to cancel the company's subscription or change its payment
       method. Added the same `org_role != "owner"` gate `/upgrade`
       already uses right above.
    3. `container.audit.log(...)` — `PlatformAudit` has no `.log()`
       method, only `log_event(event, email, organization_id,
       metadata=None)` (`email` is a required positional argument the
       spec's own call never passed at all); also called unconditionally
       with no `if container.audit is not None:` guard, which every
       other audited endpoint in this codebase uses since `audit` is an
       optional, `None`-by-default capability — would raise
       `AttributeError` on both counts, every time, for the common case
       of no audit backend configured.
    4. `request_id="req_portal"` / `execution_time=0` — hardcoded
       placeholders instead of this file's own established
       `Depends(get_request_id)` / `time.perf_counter() - start`
       pattern, used by every other endpoint here.
    5. `return_url="https://seuapp.com/billing"` — a literal placeholder
       domain hardcoded into the router. Uses `settings.
       STRIPE_PORTAL_RETURN_URL` instead, matching how `STRIPE_SUCCESS_
       URL`/`STRIPE_CANCEL_URL` are already configured.
    6. Returned a bare `dict` with no `response_model`, unlike every
       other endpoint in this file. `PortalSessionResponse` covers both
       of `create_portal_session()`'s possible shapes (`status`, plus
       either `url` or `reason`).

    `get_stripe_sync_service()` (Sprint 279, reused unchanged per this
    sprint's own "se já existir, só reutilizar" instruction — the
    spec's own Part 3 proposed a `container.stripe_sync()` method that
    doesn't exist anywhere on `PlatformContainer`) returns `None` when
    Stripe isn't configured for this deployment at all; that's a 503,
    not an attempt to fall back to some non-Stripe portal equivalent —
    there isn't one.
    """
    start = time.perf_counter()

    if tenant_id is None:
        raise HTTPException(status_code=404, detail="No organization found")

    ensure_tenant_access(session, tenant_id)

    auth = container.auth()
    org_role = auth.get_user_organization_role(session["email"])

    if org_role != "owner":
        raise HTTPException(
            status_code=403, detail="Only the organization owner can manage billing"
        )

    if stripe_sync is None:
        raise HTTPException(status_code=503, detail="Stripe is not configured")

    result = stripe_sync.create_portal_session(
        org_id=tenant_id, return_url=settings.STRIPE_PORTAL_RETURN_URL
    )

    if container.audit is not None:
        container.audit.log_event("billing_portal_created", session["email"], tenant_id, result)

    data = PortalSessionResponse(**result)

    return ApiResponse(
        success=True,
        data=data,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


class VariantMetrics(BaseModel):
    conversion_rate: float
    mrr: float


class PriceAdjustmentRecommendation(BaseModel):
    recommended_strategy: str
    confidence: float
    reason: str


class PricingInsightsResponse(BaseModel):
    experiments: dict[str, VariantMetrics]
    recommendation: PriceAdjustmentRecommendation


_PRICING_INSIGHTS_AUDIT_EVENT = "pricing_insights_access"


@router.get("/pricing-insights", response_model=ApiResponse[PricingInsightsResponse])
async def get_pricing_insights(
    session: dict = Depends(get_current_session),
    request_id: str = Depends(get_request_id),
    container: PlatformContainer = Depends(get_platform_container),
    analytics: BillingAnalytics = Depends(get_billing_analytics),
) -> ApiResponse[PricingInsightsResponse]:
    """Pricing experiment simulation + recommendation (Sprint 282) —
    `BillingAnalytics.pricing_experiment_metrics()`/`recommend_price_
    adjustment()` (not recalculated here), themselves backed by
    `PricingExperimentEngine` (app/platform/billing/pricing_experiments.py).
    Purely analytical: no organization's real `plan`, no Stripe price,
    no Stripe API call, nothing here touches any of them — this
    sprint's own explicit "zero side-effect" rule. Admin-only and
    audited, same pattern as `/billing/dashboard`/`/billing/analytics`
    right above: this aggregates every organization on the platform,
    exactly the class of cross-tenant data those endpoints are
    admin-only for (Sprint 272/273's own established precedent).
    """
    start = time.perf_counter()

    role = _require_admin(session, container)

    if container.audit is not None:
        organization_id = container.auth().get_user_organization(session["email"])
        container.audit.log_event(
            _PRICING_INSIGHTS_AUDIT_EVENT,
            session["email"],
            organization_id,
            {"role": role},
        )

    data = PricingInsightsResponse(
        experiments=analytics.pricing_experiment_metrics(),
        recommendation=analytics.recommend_price_adjustment(),
    )

    return ApiResponse(
        success=True,
        data=data,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


class RevenueActivationResponse(BaseModel):
    high_intent: list[dict]
    churn_risk: list[dict]
    expansion: list[dict]


_REVENUE_ACTIVATION_AUDIT_EVENT = "revenue_activation_access"


@router.get("/revenue-activation", response_model=ApiResponse[RevenueActivationResponse])
async def get_revenue_activation(
    session: dict = Depends(get_current_session),
    request_id: str = Depends(get_request_id),
    container: PlatformContainer = Depends(get_platform_container),
    engine: RevenueActivationEngine = Depends(get_revenue_activation_engine),
) -> ApiResponse[RevenueActivationResponse]:
    """Prioritized commercial lead lists (Sprint 283) —
    `RevenueActivationEngine.high_intent_leads()`/`churn_risk_leads()`/
    `expansion_opportunities()` (not recalculated here), each already
    scored and sorted highest-first. Purely read-only: no organization's
    `plan`, no Stripe call, nothing here mutates anything — this
    sprint's own explicit "só inteligência + priorização" rule. Admin-
    only and audited, same pattern as `/dashboard`/`/analytics`/
    `/pricing-insights` right above: this aggregates every organization
    on the platform, the same class of cross-tenant data those
    endpoints are admin-only for (Sprint 272/273's own established
    precedent).
    """
    start = time.perf_counter()

    role = _require_admin(session, container)

    if container.audit is not None:
        organization_id = container.auth().get_user_organization(session["email"])
        container.audit.log_event(
            _REVENUE_ACTIVATION_AUDIT_EVENT,
            session["email"],
            organization_id,
            {"role": role},
        )

    data = RevenueActivationResponse(
        high_intent=engine.high_intent_leads(),
        churn_risk=engine.churn_risk_leads(),
        expansion=engine.expansion_opportunities(),
    )

    return ApiResponse(
        success=True,
        data=data,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


class PlaybookEntry(BaseModel):
    org_id: str
    message: str
    action: str
    priority: int
    # Sprint 285 — needed here or response_model validation would
    # silently strip it from the response even though
    # SalesPlaybookEngine already computes it.
    state: str


class SalesPlaybookResponse(BaseModel):
    high_intent: list[PlaybookEntry]
    churn_risk: list[PlaybookEntry]
    expansion: list[PlaybookEntry]


_SALES_PLAYBOOK_AUDIT_EVENT = "sales_playbook_access"


@router.get("/sales-playbook", response_model=ApiResponse[SalesPlaybookResponse])
async def get_sales_playbook(
    session: dict = Depends(get_current_session),
    request_id: str = Depends(get_request_id),
    container: PlatformContainer = Depends(get_platform_container),
    engine: SalesPlaybookEngine = Depends(get_sales_playbook_engine),
) -> ApiResponse[SalesPlaybookResponse]:
    """Ready-to-send commercial message payloads (Sprint 284) —
    `SalesPlaybookEngine.generate_playbook()` (not recalculated here),
    itself a pure transform over `RevenueActivationEngine`'s already-
    scored lead lists (Sprint 283). Nothing here sends anything —
    no WhatsApp/email/CRM integration exists in this codebase, and this
    sprint's own explicit rules say not to build one yet. Admin-only
    and audited, same pattern as `/revenue-activation` right above:
    this aggregates every organization on the platform, the same class
    of cross-tenant data that endpoint is admin-only for.
    """
    start = time.perf_counter()

    role = _require_admin(session, container)

    if container.audit is not None:
        organization_id = container.auth().get_user_organization(session["email"])
        container.audit.log_event(
            _SALES_PLAYBOOK_AUDIT_EVENT,
            session["email"],
            organization_id,
            {"role": role},
        )

    data = SalesPlaybookResponse(**engine.generate_playbook())

    return ApiResponse(
        success=True,
        data=data,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


class PlaybookActionRequest(BaseModel):
    org_id: str
    lead_type: str
    action: str


class PlaybookActionResponse(BaseModel):
    org_id: str
    lead_type: str
    previous_state: str
    new_state: str


_LEAD_STATE_TRANSITION_AUDIT_EVENT = "lead_state_transition"


@router.post("/sales-playbook/action", response_model=ApiResponse[PlaybookActionResponse])
async def execute_playbook_action(
    body: PlaybookActionRequest,
    session: dict = Depends(get_current_session),
    request_id: str = Depends(get_request_id),
    container: PlatformContainer = Depends(get_platform_container),
    lead_tracker: LeadExecutionTracker = Depends(get_lead_execution_tracker),
) -> ApiResponse[PlaybookActionResponse]:
    """Sprint 285 — the first endpoint in the whole revenue/billing-
    intelligence stack that records a real outcome rather than only
    computing a fresh signal. `body.action` is one of `"execute"`
    (a rep acted on the offer — recorded as `"contacted"`),
    `"ignore"` (recorded as `"ignored"`), or `"convert"` (recorded as
    `"converted"`) — see `LeadExecutionTracker.record_action()`'s own
    docstring for the verb-to-noun mapping and why `(org_id, lead_type)`
    doesn't need to currently appear in a live playbook to be recorded.

    Never touches `plan`, `subscription_status`, or Stripe — this
    sprint's own explicit "no direct billing mutations" rule; the only
    state this writes is `PlatformAuth`'s new `lead_states` field.
    Admin-only, same as every other endpoint in this file that reads or
    writes cross-tenant revenue/sales data — deciding whether *we*
    contacted or converted a customer is an internal sales operation,
    not something the customer's own organization owner should see or
    control, unlike e.g. `/billing/upgrade`.
    """
    start = time.perf_counter()

    role = _require_admin(session, container)

    try:
        result = lead_tracker.record_action(body.org_id, body.lead_type, body.action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if container.audit is not None:
        container.audit.log_event(
            _LEAD_STATE_TRANSITION_AUDIT_EVENT,
            session["email"],
            body.org_id,
            {
                "role": role,
                "lead_type": result["lead_type"],
                "action": body.action,
                "previous_state": result["previous_state"],
                "new_state": result["new_state"],
            },
        )

    data = PlaybookActionResponse(**result)

    return ApiResponse(
        success=True,
        data=data,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


class LeadTypeConversionMetrics(BaseModel):
    pending: int
    contacted: int
    converted: int
    ignored: int
    conversion_rate: float


class ConversionSummaryResponse(BaseModel):
    summary: dict[str, LeadTypeConversionMetrics]


_CONVERSION_SUMMARY_AUDIT_EVENT = "conversion_summary_access"


@router.get(
    "/sales-playbook/conversion-summary", response_model=ApiResponse[ConversionSummaryResponse]
)
async def get_conversion_summary(
    session: dict = Depends(get_current_session),
    request_id: str = Depends(get_request_id),
    container: PlatformContainer = Depends(get_platform_container),
    lead_tracker: LeadExecutionTracker = Depends(get_lead_execution_tracker),
) -> ApiResponse[ConversionSummaryResponse]:
    """Basic conversion tracking (Sprint 285) —
    `LeadExecutionTracker.conversion_summary()` (not recalculated
    here), per `lead_type` state counts plus a `conversion_rate`. This
    is the raw feedback-loop material this sprint asked for, not an
    auto-tuning loop itself — see that method's own docstring for why.
    Read-only, admin-only, audited, same pattern as every other
    aggregate endpoint in this file.
    """
    start = time.perf_counter()

    role = _require_admin(session, container)

    if container.audit is not None:
        organization_id = container.auth().get_user_organization(session["email"])
        container.audit.log_event(
            _CONVERSION_SUMMARY_AUDIT_EVENT,
            session["email"],
            organization_id,
            {"role": role},
        )

    data = ConversionSummaryResponse(summary=lead_tracker.conversion_summary())

    return ApiResponse(
        success=True,
        data=data,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


class WeeklyFocus(BaseModel):
    org_id: str | None
    type: str | None
    priority_score: float | None
    recommended_action: str | None
    message: str


class BusinessOverviewResponse(BaseModel):
    mrr: int
    active_customers: int
    churn_rate: float
    # Sprint 287 — composite business health score/status, see
    # BusinessOverviewEngine.business_score()'s own docstring.
    business_score: int
    business_status: str
    top_opportunities: list[dict]
    # Sprint 287 renamed from "high_risk_customers"; entries now carry
    # "priority_score" (float) instead of the old "priority" string, and
    # a new "revenue_at_risk" field.
    at_risk_customers: list[dict]
    # Sprint 287 — new: paying organizations ranked by MRR contribution.
    top_customers: list[dict]
    conversion_summary: dict[str, LeadTypeConversionMetrics]
    weekly_focus: WeeklyFocus
    executive_insight: str


_BUSINESS_OVERVIEW_AUDIT_EVENT = "business_overview_access"


@router.get("/overview", response_model=ApiResponse[BusinessOverviewResponse])
async def get_billing_overview(
    session: dict = Depends(get_current_session),
    request_id: str = Depends(get_request_id),
    container: PlatformContainer = Depends(get_platform_container),
    engine: BusinessOverviewEngine = Depends(get_business_overview_engine),
) -> ApiResponse[BusinessOverviewResponse]:
    """Nexara's main entry point (Sprint 286, refined into a "premium
    business intelligence layer" Sprint 287) —
    `BusinessOverviewEngine.generate_overview()` (not recalculated
    here), a single read-only aggregation over `BillingAnalytics`
    (Sprint 274), `RevenueActivationEngine` (Sprint 283), and
    `LeadExecutionTracker` (Sprint 285). No new prediction, scoring, or
    billing/Stripe logic exists anywhere in this endpoint or the engine
    behind it — every Sprint 287 addition is either read straight from
    those three, or a documented composite of two or more of their
    already-computed numbers (see `BusinessOverviewEngine`'s own
    docstring). `top_opportunities`/`at_risk_customers` entries each
    carry a `priority_score` (numeric, replacing Sprint 286's
    categorical `priority`) and `recommended_action` derived from it;
    `business_score`/`business_status` summarize overall health;
    `top_customers` ranks paying organizations by real MRR
    contribution; `weekly_focus` is the single highest-priority item
    across the two actionable lists; `executive_insight` is one
    deterministic, template-composed sentence over already-known
    numbers — no LLM or external call anywhere, this sprint's own
    explicit rule.

    Admin-only and audited, same pattern as every other cross-tenant
    aggregate endpoint in this file — this is the broadest aggregation
    of them all, spanning billing, revenue, churn, and conversion data
    for every organization on the platform at once.
    """
    start = time.perf_counter()

    role = _require_admin(session, container)

    if container.audit is not None:
        organization_id = container.auth().get_user_organization(session["email"])
        container.audit.log_event(
            _BUSINESS_OVERVIEW_AUDIT_EVENT,
            session["email"],
            organization_id,
            {"role": role},
        )

    data = BusinessOverviewResponse(**engine.generate_overview())

    return ApiResponse(
        success=True,
        data=data,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )
