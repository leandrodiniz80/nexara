"""Tenant onboarding + self-service domains + plan limits (Sprint 265).

Major architectural deviation from the spec, deliberate and documented
here rather than silently built as specified:

The spec's own design introduces a brand-new `container.tenant()`
service (`create_tenant()`, `add_domain()`, `get_domains()`) and a new
`container.plan()` / `PlanManager` (Redis-backed, `tenant:plan:{id}`)
as if neither concept exists yet. Both already do, more completely:

- "Tenant" is `organization_id` throughout this entire platform — every
  sprint since 254 has used `tenant_id` as a synonym for it,
  `PlatformContainer` already has `set_tenant()`/`get_tenant_id()`/
  `ensure_same_tenant()` built on exactly that, and domain ownership is
  already tracked by `DomainTenantResolver` (`register_domain()`/
  `get_owner()`/`get_domains_for_organization()` — `get_owner()`'s own
  docstring even already says it's "used by the registration endpoint to
  detect domain takeover attempts before writing", i.e. it was already
  built for the exact self-service endpoint this sprint adds).
- `PlatformAuth` already has a complete plan system: `_DEFAULT_PLANS`
  (free/pro/enterprise), `create_organization()` (with a name),
  `get_organization_plan()`/`set_organization_plan()`/`get_plan_limits()`,
  even `check_limit()`/`increment_usage()` for other limit types. It was
  missing only two limit keys (`domains`, `alerts_per_hour` — added to
  `_DEFAULT_PLANS` this sprint) and a way to rename an organization after
  creation (`rename_organization()`, added this sprint).

Building the spec's own parallel `Tenant`/`PlanManager` entities would
mean two independent sources of truth for the same data (an
organization's name, domain list, and — most importantly, given Sprint
266 is explicitly "Billing (Stripe)" — its *plan*) that could silently
drift out of sync. This file is a thin, additive layer over the
already-established `PlatformAuth`/`DomainTenantResolver`, not a new
subsystem.

Mounted at `/tenants` (not `/org`, where `GET /org/me` already exposes
similar organization data via a different, pre-existing router using the
`ApiResponse[T]` convention): kept separate rather than folding into
`organizations.py` to avoid risking an unfamiliar, already-established
router this session has never touched, and because `tenant_id`/`/tenants`
terminology is already how this exact subsystem (`cdn.py`'s metrics/
alerts endpoints) refers to the same concept. Worth reconciling
`/tenants` and `/org` into one router in a future sprint; flagged here
rather than silently duplicated without comment, the same as Sprint
264's `Page`/`PageMetadata` finding.

Sprint 266 adds API-key CRUD (`/api-keys`) to this same router — see
`app/platform/tenant/api_key_manager.py` and `app/api/dependencies/
api_keys.py` for the key-management/dependency-wiring side, and
`cdn.py`'s `_resolve_scope_with_api_key()` for how `/metrics/alerts`,
`/metrics/live-status`, and `/metrics/chart/{domain}` accept either a
session or an API key.

Sprint 270 adds `/usage`; Sprint 271 adds `/usage/alerts` (soft-limit /
upgrade-nudge signaling, purely informational — see
`app/platform/usage/usage_alerts.py`'s own docstring for why `UsageAlerts`
is constructed here in the router rather than wired as a storage
capability the way that sprint's own spec proposed).

Sprint 278 adds `/auto-actions` (read-only dry-run) and `/auto-actions/
apply` (the only place in this codebase that executes
`BillingDecisionEngine`'s proposed plan mutations) — see
`app/platform/billing/decision_engine.py`'s own docstring for the
dry-run/execute split and Stripe-safety guards, both decided explicitly
by the user rather than the sprint's own original "execute
automatically inside a GET" framing.

Sprint 279 wires real Stripe execution into that same endpoint (no new
routes) — `StripeSyncService` (`app/platform/billing/stripe_sync.py`)
routes any Stripe-bound organization's upgrade through Stripe instead of
a direct internal plan change, per the user's own explicit "Stripe é a
fonte da verdade para billing" decision. `apply()`'s response gained a
`"pending_checkout"` bucket for upgrades that need a customer to
complete Stripe Checkout before anything actually changes — see
`apply_auto_actions()`'s own docstring below.

Sprint 280 added self-serve billing management (`POST /billing/portal`,
not this router) via the Stripe Customer Portal — customers now cancel/
downgrade/change payment methods themselves. Per the user's own
follow-up decision, Sprint 281 removed downgrade *execution* from
`BillingDecisionEngine` entirely: `apply()`'s response now has
`"downgrade_recommendations"` instead of `"downgrades"`, and nothing in
that bucket is ever actually applied, by anything, regardless of
`execute` — see `decision_engine.py`'s own module docstring. Sprint 281
also added optional `NotificationService` signaling
(`upgrade_recommended`/`checkout_pending`/`churn_risk`), fired only from
`apply()`, never the dry-run.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.dependencies.api_keys import get_api_key_manager
from app.api.dependencies.auth import get_current_session, get_platform_container
from app.api.dependencies.billing import get_decision_engine
from app.api.dependencies.metrics import get_metrics_store
from app.api.dependencies.tenant_resolver import DomainTenantResolver, get_domain_tenant_resolver
from app.core.config import settings
from app.platform.billing.decision_engine import BillingDecisionEngine
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.metrics.loader_metrics import LoaderMetricsStore
from app.platform.tenant.api_key_manager import ApiKeyManager, mask_api_key
from app.platform.usage.usage_alerts import UsageAlerts

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/tenants", tags=["Tenants"])


def _require_own_tenant_id(session: dict, container: PlatformContainer) -> str:
    tenant_id = container.auth().get_user_organization(session["email"])

    if tenant_id is None:
        raise HTTPException(status_code=404, detail="No organization found")

    return tenant_id


def _require_owner(session: dict, container: PlatformContainer) -> None:
    """Same gate `PlatformContainer.upgrade_plan()` already applies to
    changing an organization's plan — renaming the organization or
    registering a domain (which consumes shared, plan-limited quota) is
    the same class of sensitive, org-wide action, not something every
    member should be able to do unilaterally.
    """
    if container.auth().get_user_organization_role(session["email"]) != "owner":
        raise HTTPException(
            status_code=403, detail="Only the organization owner can perform this action"
        )


def _require_admin_or_owner_scope(session: dict, container: PlatformContainer) -> str | None:
    """Sprint 278. Returns `None` when the caller is a platform admin
    (unrestricted — same global `role == "admin"` check as `_require_admin`
    in cdn.py), or the caller's own `organization_id` when they're merely
    that organization's owner; every other caller gets a 403.

    `/tenants/auto-actions` and `/tenants/auto-actions/apply` span every
    organization on the platform by default (`BillingDecisionEngine.run()`
    iterates `list_organizations()`, same shape as `/billing/analytics`,
    Sprint 272/273's admin-only precedent for exactly this kind of
    aggregate data) — an owner may only ever see or apply actions for
    their *own* organization, never anyone else's, or this would be the
    same cross-tenant leak `/billing/dashboard`/`/billing/analytics` were
    built admin-only specifically to avoid. The spec's own "apenas admin
    OU owner" security line, read literally with no further scoping,
    would let any organization owner see every other tenant's proposed
    billing actions — this is that requirement's actual safe
    implementation.
    """
    role = container.auth().get_user_role(session["email"])

    if role == "admin":
        return None

    org_id = container.auth().get_user_organization(session["email"])
    org_role = container.auth().get_user_organization_role(session["email"])

    if org_id is not None and org_role == "owner":
        return org_id

    raise HTTPException(status_code=403, detail="Admin or organization owner required")


class CreateTenantRequest(BaseModel):
    name: str


@router.post("")
async def create_tenant(
    body: CreateTenantRequest,
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
) -> dict:
    """Names the caller's own organization (auto-created at registration
    with a placeholder name, `f"{email}'s organization"`) — not creating
    a brand-new "tenant" entity, since the organization already exists;
    see this module's own docstring for why. `tenant_id` in the response
    is simply that organization's id.
    """
    tenant_id = _require_own_tenant_id(session, container)
    _require_owner(session, container)

    container.auth().rename_organization(tenant_id, body.name)

    return {"tenant_id": tenant_id, "name": body.name}


class AddDomainRequest(BaseModel):
    domain: str


@router.post("/domains")
async def add_tenant_domain(
    body: AddDomainRequest,
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    resolver: DomainTenantResolver = Depends(get_domain_tenant_resolver),
) -> dict:
    """Self-service domain registration against the caller's own
    organization, backed by the already-established
    `DomainTenantResolver` (unchanged — see this module's own docstring).

    Security, per this sprint's own explicit requirements:
    - Normalizes via `strip().lower()` before every check and the write
      itself — `DomainTenantResolver.register_domain()` already lowercases
      internally, but not the pre-check `get_owner()` lookup below unless
      the caller does it first, and it never strips whitespace at all.
    - Rejects an already-registered domain outright — 409 if it's already
      the caller's own (a clear, actionable "you already did this"), 403
      if it belongs to a different organization (a domain-takeover
      attempt, not a "resource already exists" situation — a 409 there
      would leak that the domain is registered to *someone*, a minor but
      real information disclosure `get_owner()`'s own docstring already
      anticipates guarding against).
    - Enforces the plan's `domains` limit (Sprint 265) before writing —
      `-1` is this platform's established "unlimited" sentinel
      (`PlatformAuth.check_limit()`'s own convention), not a large finite
      number.
    """
    tenant_id = _require_own_tenant_id(session, container)
    _require_owner(session, container)

    domain = body.domain.strip().lower()

    if not domain:
        raise HTTPException(status_code=422, detail="Domain cannot be empty")

    existing_owner = resolver.get_owner(domain)

    if existing_owner == tenant_id:
        raise HTTPException(
            status_code=409, detail="Domain already registered to your organization"
        )

    if existing_owner is not None:
        raise HTTPException(
            status_code=403, detail="Domain already registered to another organization"
        )

    plan = container.auth().get_organization_plan(tenant_id)
    domain_limit = container.auth().get_plan_limits(plan).get("domains")
    current_domain_count = len(resolver.get_domains_for_organization(tenant_id))

    if domain_limit is not None and domain_limit != -1 and current_domain_count >= domain_limit:
        raise HTTPException(status_code=403, detail="Domain limit reached for your plan")

    resolver.register_domain(domain, tenant_id)

    return {"status": "ok", "domain": domain}


@router.get("/plan")
async def get_tenant_plan(
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
) -> dict:
    tenant_id = _require_own_tenant_id(session, container)

    plan = container.auth().get_organization_plan(tenant_id)
    limits = container.auth().get_plan_limits(plan)

    return {"plan": plan, "limits": limits}


# --- API keys (Sprint 266) ------------------------------------------------
#
# Owner-only, same gate as renaming the organization or registering a
# domain above: an API key grants programmatic access to the tenant's
# data, at least as sensitive an action as either of those.


@router.post("/api-keys")
async def create_api_key(
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    api_key_manager: ApiKeyManager = Depends(get_api_key_manager),
) -> dict:
    """Response contract unchanged from Sprint 266 (`{"api_key": key}`,
    the full raw value) — this sprint's own explicit "don't change the
    creation response contract" rule.

    Audited (Sprint 267) via the masked value, not the raw key — an
    audit trail that itself logged the full secret would defeat the
    entire point of never persisting it. Guarded by
    `if container.audit is not None`, matching every other audit call
    site in this codebase (`container.audit` legitimately defaults to
    `None`; the spec's own version called `container.audit.log_event()`
    unconditionally, an `AttributeError` whenever it isn't configured).
    Also passes `organization_id=tenant_id` as `log_event()`'s own
    signature requires — a required positional argument the spec's
    version omitted entirely (`TypeError` on every call as written).
    """
    tenant_id = _require_own_tenant_id(session, container)
    _require_owner(session, container)

    key = api_key_manager.generate_key(tenant_id)

    if container.audit is not None:
        container.audit.log_event(
            "api_key_created", session["email"], tenant_id, {"masked_key": mask_api_key(key)}
        )

    return {"api_key": key}


@router.get("/api-keys")
async def list_api_keys(
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    api_key_manager: ApiKeyManager = Depends(get_api_key_manager),
) -> dict:
    """`items` shape changed in Sprint 267: was `list[str]` (the raw key
    values, per Sprint 266), now `list[dict]` (`{"key": masked,
    "created_at": ...}`) — a deliberate, expected breaking change to this
    one response (this sprint's own explicit goal is that a listing must
    never expose a full key again), unlike `create_api_key()`'s
    unchanged contract.
    """
    tenant_id = _require_own_tenant_id(session, container)
    _require_owner(session, container)

    return {"items": api_key_manager.list_keys(tenant_id)}


class RevokeKeyRequest(BaseModel):
    key: str


@router.delete("/api-keys")
async def revoke_api_key(
    body: RevokeKeyRequest,
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    api_key_manager: ApiKeyManager = Depends(get_api_key_manager),
) -> dict:
    """404, not a silent no-op, when `body.key` doesn't belong to the
    caller's own tenant (including when it doesn't exist at all, or
    belongs to someone else) — `ApiKeyManager.revoke_key()`'s own
    ownership check (Sprint 266's fix for the spec's unconditional-delete
    bug) is what makes this safe to expose without first listing the
    caller's own keys to compare against.
    """
    tenant_id = _require_own_tenant_id(session, container)
    _require_owner(session, container)

    if not api_key_manager.revoke_key(tenant_id, body.key):
        raise HTTPException(status_code=404, detail="API key not found")

    if container.audit is not None:
        container.audit.log_event(
            "api_key_revoked",
            session["email"],
            tenant_id,
            {"masked_key": mask_api_key(body.key)},
        )

    return {"status": "revoked"}


@router.get("/usage")
async def get_tenant_usage(
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Sprint 270. Fixes from the spec's own router code:

    1. `Depends(get_container)` — no such dependency exists; the real
       name (used by every other endpoint in this file) is
       `get_platform_container`.
    2. `container.metrics_store()` — `PlatformContainer` has no such
       method; the metrics store is its own FastAPI dependency
       (`get_metrics_store`, `app/api/dependencies/metrics.py`), the same
       one every `/cdn/metrics/*` endpoint already injects.
    3. `container.metrics_store()._storage` — reaches straight past the
       store into its private `_storage`, the exact encapsulation break
       this sprint's own rules explicitly forbid ("Não acessar `_storage`
       direto no router"). Fixed via `store.get_usage()`, the same
       public-delegation pattern already used for
       `get_digest_size()`/`webhook_queue_status()`/etc.

    Returns `0` for `alerts_sent` (not an error) when no `usage_tracker`
    is configured — same "optional capability, no crash" convention as
    every other read here.
    """
    tenant_id = _require_own_tenant_id(session, container)

    return {"usage": {"alerts_sent": store.get_usage(tenant_id, "alerts_sent")}}


@router.get("/usage/alerts")
async def get_usage_alerts(
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Soft-limit / upgrade-nudge signal (Sprint 271) — `{"alerts": null}`
    when usage is comfortably under the plan's limit, otherwise
    `{"alerts": {"level": "warning"|"hard_limit", "used", "limit",
    "message"}}`. Never blocks anything: purely informational, meant for
    a UI banner or an upgrade nudge.

    Fixes from the spec's own router code:

    1. `getattr(store._storage, "usage_alerts", None)` — reaches straight
       past `store` into its private `_storage`, the exact encapsulation
       break this sprint's own rules explicitly forbid. `UsageAlerts` is
       constructed right here instead, from `store.get_usage` and
       `container.auth().get_usage_limit` (both already-established
       public methods) — see `usage_alerts.py`'s own docstring for why
       it isn't wired as a storage capability the way the spec's Part 5
       proposed (metrics storage has no access to `PlatformAuth`, and
       none of this reads Redis directly anyway, so there's no capability
       to wire in the first place).
    2. `tenant_id = container.auth().get_user_organization(...)` used
       directly, with no check for `None` (no organization) — silently
       proceeds and always resolves to "no alert" rather than surfacing
       the real problem. Uses `_require_own_tenant_id()` instead, the
       same helper (and same 404) every other endpoint in this file
       already uses for a caller with no organization.
    3. `check_threshold(tenant_id, "alerts_sent")` — `UsageTracker`
       (Sprint 270) tracks alerts under `"alerts_sent"`, but
       `PlatformAuth`'s plan limits (Sprint 265) store the cap under
       `"alerts_per_hour"`; a single shared metric name would make
       `get_usage_limit()` miss its own key and always report
       "unlimited". Passes both metric names explicitly instead — see
       `check_threshold()`'s own docstring in usage_alerts.py.
    """
    tenant_id = _require_own_tenant_id(session, container)

    usage_alerts = UsageAlerts(store.get_usage, container.auth().get_usage_limit)
    result = usage_alerts.check_threshold(tenant_id, "alerts_sent", "alerts_per_hour")

    return {"alerts": result}


@router.get("/auto-actions")
async def get_auto_actions(
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    engine: BillingDecisionEngine = Depends(get_decision_engine),
) -> dict:
    """Read-only dry-run (Sprint 278) — `{"upgrades": [...],
    "downgrade_recommendations": [...], "retention": [...]}`, the
    auto-upgrade/downgrade-recommendation/retention-flag actions
    `BillingDecisionEngine` would propose right now (downgrades are
    signal-only as of Sprint 281 — never executed by anything, even via
    `apply()` below; see decision_engine.py's own module docstring).
    Never mutates anything: `engine.run()` defaults to `execute=False`.
    Admins see every organization's proposal; owners see only their own
    organization's (see `_require_admin_or_owner_scope()`'s own
    docstring for why an owner can't see every tenant's proposed actions
    here).

    Safe to call anytime, any number of times — see `POST /auto-actions/
    apply` for the explicit, audited, execute=True path. This endpoint
    itself never reaches it.
    """
    scope_org_id = _require_admin_or_owner_scope(session, container)

    return engine.run(org_id=scope_org_id)


class ApplyAutoActionsRequest(BaseModel):
    org_id: str | None = None
    action_type: str | None = None


@router.post("/auto-actions/apply")
async def apply_auto_actions(
    body: ApplyAutoActionsRequest,
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    engine: BillingDecisionEngine = Depends(get_decision_engine),
) -> dict:
    """Explicit execution (Sprint 278, real Stripe execution wired in
    Sprint 279, downgrade execution removed Sprint 281) — the only
    endpoint in this codebase that mutates organization plans, whether
    directly or by routing through Stripe, via `BillingDecisionEngine`
    (`engine.run(execute=True, ...)`). Never reachable from the
    read-only `GET /auto-actions` dry-run above.

    `body.org_id`/`body.action_type` narrow which proposed actions
    actually get applied (`action_type` one of `"upgrade"`,
    `"downgrade"`, `"retention_flag"` — `"downgrade"` still filters
    correctly, it just never results in anything being applied; see
    below). An organization owner (as opposed to a platform admin) can
    only ever apply actions for their *own* organization — attempting a
    different `org_id` is rejected outright, rather than silently
    substituting their own org_id in its place, so a caller never gets a
    different result than what they explicitly asked for.

    Response shape now includes a `"pending_checkout"` bucket alongside
    `"upgrades"`/`"downgrade_recommendations"`/`"retention"` (Sprint
    279, per the user's own explicit decision): an upgrade for an
    organization with no active Stripe subscription creates a Checkout
    Session rather than granting access outright — there's no browser in
    this call path to redirect to it, and nothing here can safely assume
    the customer will ever complete it — so it's reported as `{"org_id",
    "action": "upgrade", "checkout_url", "reason": "requires_customer_
    action"}`, never folded into `"upgrades"` as if the plan had actually
    changed. No plan mutation occurs for it; an admin can act on the
    returned `checkout_url` manually (e.g. forward it to the customer).

    `"downgrade_recommendations"` (renamed from `"downgrades"`, Sprint
    281): now that Sprint 280 gave customers a self-serve Stripe Customer
    Portal for managing their own subscription, downgrades are *never*
    executed here, by anything, `execute=True` or not — see
    decision_engine.py's own module docstring. This bucket is always
    exactly what `auto_downgrade()` proposed, verbatim, whether this call
    reads or executes.

    `NotificationService` signaling (Sprint 281, stub — no real email/
    WhatsApp/CRM integration yet) fires for each organization actually
    upgraded (`upgrade_recommended`), each that got a pending checkout
    instead (`checkout_pending`), and each newly flagged for retention
    (`churn_risk`) — never for downgrade recommendations (not part of
    the 3-event list this sprint asked for, and the stub has no dedup
    mechanism, so notifying on every recommended downgrade on every call
    would mean unbounded repeat notifications for the same organization).

    Every actually-applied (or pending) action is audited individually
    (`billing_auto_action`, one `PlatformAudit` event per action,
    including `checkout_url` when present, not one bundled event for the
    whole call) — matches this codebase's own convention of one
    specific, queryable event per action rather than a generic catch-all
    (see billing.py's own `_STRIPE_EVENT_AUDIT_NAMES` for the same
    reasoning). Only actions `engine.run()` itself reports back as
    actually applied or pending are audited — an action skipped by the
    engine's own re-validation (e.g. the org's state drifted since the
    last dry-run, or it's Stripe-bound with no Stripe sync configured)
    is not logged as if it had happened, and `"downgrade_recommendations"`
    is excluded from this loop entirely (Sprint 281): every entry there
    is always exactly what was proposed, never something this endpoint
    did, so auditing it as a `billing_auto_action` would misrepresent a
    recommendation as an action taken.
    """
    scope_org_id = _require_admin_or_owner_scope(session, container)

    if scope_org_id is not None:
        if body.org_id is not None and body.org_id != scope_org_id:
            raise HTTPException(
                status_code=403,
                detail="Owners may only apply actions for their own organization",
            )
        org_id = scope_org_id
    else:
        org_id = body.org_id

    applied = engine.run(execute=True, org_id=org_id, action_type=body.action_type)

    if container.audit is not None:
        audited_buckets = ("upgrades", "retention", "pending_checkout")

        for bucket in audited_buckets:
            for action in applied[bucket]:
                container.audit.log_event(
                    "billing_auto_action",
                    session["email"],
                    action["org_id"],
                    {
                        "action": action["action"],
                        "from": action.get("from"),
                        "to": action.get("to"),
                        "reason": action["reason"],
                        "checkout_url": action.get("checkout_url"),
                    },
                )

    return applied
