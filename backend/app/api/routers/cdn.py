import gzip
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel

from app.api.dependencies.api_keys import get_optional_api_key_tenant
from app.api.dependencies.auth import (
    get_current_session,
    get_optional_session,
    get_platform_container,
)
from app.api.dependencies.metrics import get_metrics_store
from app.api.dependencies.tenant import get_request_tenant_id
from app.api.dependencies.tenant_context_guard import ensure_tenant_access
from app.api.dependencies.tenant_resolver import DomainTenantResolver, get_domain_tenant_resolver
from app.core.config import settings
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.metrics.loader_metrics import LoaderMetricsStore

logger = logging.getLogger("app.api.cdn")

_CDN_DIR = Path(__file__).resolve().parents[3] / "cdn"

# Every loader file this router can serve. Adding a new version later is one
# more entry here plus the file itself in cdn/ — the caching, gzip and
# serving logic below is fully generic across versions, nothing else to
# touch. Once a version ships, its file must never change in place: it's
# served with `Cache-Control: immutable` (see `/loader.v1.js` below), so any
# CDN/browser that already fetched it will never re-request it within the
# max-age window — a real change belongs in a new version, e.g. loader.v2.js.
_LOADER_VERSIONS = {
    "v1": "loader.v1.js",
}

# Which version "/cdn/loader" (the always-latest, non-cacheable discovery
# endpoint) currently points at. Bump this when a new version is ready for
# rollout — existing "/cdn/loader.v1.js" callers are entirely unaffected.
_CURRENT_VERSION = "v1"


def _load_versions() -> tuple[dict[str, bytes], dict[str, bytes]]:
    # Read once at import time, not per request: these are served as
    # immutable, cache-forever assets, so re-reading them from disk on every
    # hit would only add blocking file I/O to the highest-traffic endpoints
    # in the whole API for zero benefit. Anchored to this file's own
    # location rather than a relative "cdn/..." path, which would break if
    # the process's working directory ever differs from the repo root.
    raw: dict[str, bytes] = {}
    gzipped: dict[str, bytes] = {}

    for version, filename in _LOADER_VERSIONS.items():
        content = (_CDN_DIR / filename).read_bytes()
        raw[version] = content
        gzipped[version] = gzip.compress(content)

    return raw, gzipped


_LOADER_CACHE, _LOADER_GZIP_CACHE = _load_versions()


def _etag_for(content: bytes) -> str:
    """MD5 is fine here — this is an ETag/cache-validation fingerprint, not a
    security boundary, same reasoning as `BrandingService.get_theme_hash()`.
    Deliberately NOT Python's built-in `hash()`: str/bytes hashing is
    randomized per-process (PYTHONHASHSEED) since Python 3.3, so the same
    bytes would get a different ETag on every restart — and could even
    differ between worker processes serving the identical file at the same
    moment, breaking CDN/edge cache validation entirely.
    """
    return f'W/"{hashlib.md5(content).hexdigest()}"'


def _serve_loader(version: str, accept_encoding: str, cache_control: str) -> Response:
    use_gzip = "gzip" in accept_encoding.lower()
    content = _LOADER_GZIP_CACHE[version] if use_gzip else _LOADER_CACHE[version]

    headers = {
        "Cache-Control": cache_control,
        "ETag": _etag_for(content),
        "Vary": "Accept-Encoding",
    }

    if use_gzip:
        headers["Content-Encoding"] = "gzip"

    return Response(content=content, media_type="application/javascript", headers=headers)


router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/cdn", tags=["CDN"])


@router.get("/loader.v1.js")
async def get_loader_v1(request: Request) -> Response:
    accept_encoding = request.headers.get("accept-encoding", "")

    return _serve_loader("v1", accept_encoding, "public, max-age=31536000, immutable")


@router.get("/loader")
async def get_loader_latest(request: Request) -> Response:
    """Always serves whichever version `_CURRENT_VERSION` currently points
    at, with `Cache-Control: no-cache` — never served stale from a CDN/
    browser cache, so a rollout to a new version reaches callers of this URL
    on their very next request. `/loader.v1.js` (and any future
    `/loader.v{n}.js`) is the CDN-safe, cache-forever alternative for
    integrators who want to pin an exact version.
    """
    accept_encoding = request.headers.get("accept-encoding", "")

    return _serve_loader(_CURRENT_VERSION, accept_encoding, "no-cache")


@router.post("/metrics")
async def ingest_loader_metrics(
    request: Request,
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Fire-and-forget telemetry ingestion for the loader (success/error
    events, fetch duration) — unauthenticated by design: the loader runs on
    arbitrary anonymous customer pages with no session, and nothing in this
    payload is sensitive (domain, timing, an error string). Never raises:
    a public, unauthenticated endpoint that 500s on malformed input is both
    a data-quality and a minor abuse concern, so any shape of bad input just
    gets acknowledged and dropped rather than surfaced as an error.
    """
    try:
        payload = await request.json()
    except Exception:
        return {"ok": False}

    if not isinstance(payload, dict):
        return {"ok": False}

    log_entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": payload.get("event"),
        "domain": payload.get("domain"),
        "version": payload.get("version"),
        "duration": payload.get("duration"),
        "error": payload.get("error"),
        "ua": request.headers.get("user-agent"),
    }

    logger.info("LOADER_METRIC: %s", json.dumps(log_entry, ensure_ascii=False))
    store.add(log_entry)

    return {"ok": True}


def _resolve_metrics_scope(
    session: dict,
    tenant_id: str | None,
    container: PlatformContainer,
    resolver: DomainTenantResolver,
) -> tuple[list[str], str, str | None]:
    """(domains, scope, role) for every `/metrics/*` list/aggregate endpoint
    below that scopes by a set of domains (dashboard, dashboard/window,
    alerts, incidents, incidents/active) — `"global"` (every domain on the
    platform) for a `role == "admin"` caller (Sprint 254), `"tenant"`
    (only the caller's own organization's domains) otherwise. Factored out
    once rather than repeated per endpoint: this is the single
    security-relevant decision every one of these endpoints makes, and
    duplicating it five times risks one of them silently drifting out of
    sync with the others. `role` is returned alongside so callers can audit
    a `"global"` access (Sprint 255) without a second, redundant lookup.

    `role == "admin"` is safe to trust here specifically because
    self-registration can no longer self-escalate to it once any admin
    exists on the platform (see `POST /auth/register`) — before that fix,
    gating a cross-tenant view on this same client-supplied field would
    have let anyone grant themselves it by registering a new account.

    Skips `ensure_tenant_access()` for admins: that check exists to catch
    a mismatch between the session's own org and a specific `tenant_id`
    being asserted — meaningless for a caller who isn't claiming
    single-tenant access at all.
    """
    role = container.auth().get_user_role(session["email"])

    if role == "admin":
        return resolver.get_all_domains(), "global", role

    if tenant_id is None:
        return [], "tenant", role

    ensure_tenant_access(session, tenant_id)

    return resolver.get_domains_for_organization(tenant_id), "tenant", role


def _resolve_scope_with_api_key(
    api_key_tenant: str | None,
    session: dict | None,
    tenant_id: str | None,
    container: PlatformContainer,
    resolver: DomainTenantResolver,
) -> tuple[list[str], str, str | None]:
    """Sprint 266: lets `/metrics/alerts`, `/metrics/live-status`, and
    `/metrics/chart/{domain}` accept either a valid `X-API-Key` header or
    a session — not a replacement for `_resolve_metrics_scope()`, an
    additional path in front of it.

    An API key is *always* `"tenant"` scope, `role=None` — never
    `"global"`, regardless of whether the underlying organization happens
    to have an admin user: a machine credential scoped to one tenant must
    never reach another tenant's data, the sprint's own explicit
    requirement. This bypasses `_resolve_metrics_scope()`'s own
    session/role-based logic entirely for that case (there is no
    `session["email"]` to look a role up for), going straight to
    `resolver.get_domains_for_organization()`.

    Falls back to the existing, unchanged `_resolve_metrics_scope()` when
    no API key was presented — 401 here, not a `TypeError` from passing
    `None` into a function that expects a real session dict, when neither
    auth method was provided at all.
    """
    if api_key_tenant is not None:
        return resolver.get_domains_for_organization(api_key_tenant), "tenant", None

    if session is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return _resolve_metrics_scope(session, tenant_id, container, resolver)


_GLOBAL_ACCESS_AUDIT_EVENT = "metrics_global_access"


def _audit_global_access(
    container: PlatformContainer,
    session: dict,
    tenant_id: str | None,
    role: str | None,
    resource: str,
) -> None:
    """Records a cross-tenant read (Sprint 255) via the platform's own,
    already-established audit trail (`PlatformAudit`, used throughout this
    codebase for registration/login/plan-upgrade events) rather than a new,
    parallel Redis-backed audit system: a second, unrelated audit trail
    would fragment exactly the "who accessed what, when" record this
    feature exists to provide for compliance (SOC2/LGPD) purposes — the
    opposite of what a unified audit trail is for. Deliberately minimal
    metadata (role, resource, scope) — no request/response bodies, no
    business data.

    A no-op if `container.audit` isn't configured (matches the
    already-established `if self.audit is not None` guard pattern used
    everywhere else in `PlatformContainer`) — auditing a read must never be
    able to break the read itself.
    """
    if container.audit is None:
        return

    container.audit.log_event(
        _GLOBAL_ACCESS_AUDIT_EVENT,
        session["email"],
        tenant_id,
        {"role": role, "resource": resource, "scope": "global"},
    )


@router.get("/metrics/summary")
async def get_metrics_summary(
    domain: str | None = None,
    session: dict = Depends(get_current_session),
    tenant_id: str | None = Depends(get_request_tenant_id),
    resolver: DomainTenantResolver = Depends(get_domain_tenant_resolver),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Authenticated — unlike ingestion, this reads back aggregate business
    data (traffic volume, error rate, latency) that's sensitive per tenant:
    an anonymous, unauthenticated caller must not be able to query an
    arbitrary domain string and learn another organization's usage/
    reliability numbers. Filtering by `domain` additionally requires the
    caller's own organization to own that domain (same ownership check as
    domain registration, Sprint 236) — an authenticated user from Org B
    still can't read Org A's per-domain stats just by guessing its domain.
    """
    if domain is not None:
        if tenant_id is None:
            raise HTTPException(status_code=404, detail="No organization found")

        ensure_tenant_access(session, tenant_id)

        if resolver.get_owner(domain) != tenant_id:
            raise HTTPException(
                status_code=403, detail="Domain not owned by your organization"
            )

    return store.summary(domain)


@router.get("/metrics/dashboard")
async def get_metrics_dashboard(
    limit: int = 10,
    offset: int = 0,
    session: dict = Depends(get_current_session),
    tenant_id: str | None = Depends(get_request_tenant_id),
    container: PlatformContainer = Depends(get_platform_container),
    resolver: DomainTenantResolver = Depends(get_domain_tenant_resolver),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Scoped to the caller's own organization — Sprint 247 shipped this
    endpoint ranking every domain on the platform for any authenticated
    user, a real cross-tenant data leak (traffic volume, error rate,
    latency for every other tenant's domains). Fixed by looking up exactly
    the domains the caller's organization owns (`DomainTenantResolver`,
    same registry used for domain registration/`/metrics/summary`'s
    ownership check) and fetching stats only for those — not by ranking
    the whole platform and filtering the result down, which would silently
    drop one of the caller's own domains if it happened to fall outside an
    arbitrary top-N cutoff before filtering.

    A platform-wide view (`role == "admin"`, see `_resolve_metrics_scope()`)
    is reachable now (Sprint 254) — additive to the response via `scope`,
    the existing tenant-scoped contract for every other caller is
    unchanged. That access is itself audited (Sprint 255) when it happens.
    """
    domains, scope, role = _resolve_metrics_scope(session, tenant_id, container, resolver)

    if scope == "global":
        _audit_global_access(container, session, tenant_id, role, "metrics.dashboard")

    if not domains:
        return {"items": [], "total": 0, "limit": limit, "offset": offset, "scope": scope}

    items = store.domains_summary(domains)

    # Deterministic even when totals tie: highest volume first, then lowest
    # error rate, then domain name — never dependent on dict/set iteration
    # order.
    items.sort(key=lambda item: (-item["total"], item["error_rate"] or 0, item["domain"]))

    total_items = len(items)
    paginated = items[offset : offset + limit]

    return {
        "items": paginated,
        "total": total_items,
        "limit": limit,
        "offset": offset,
        "scope": scope,
    }


_MAX_WINDOW_HOURS = 24 * 30


@router.get("/metrics/dashboard/window")
async def get_metrics_dashboard_window(
    hours: int = 24,
    limit: int = 10,
    offset: int = 0,
    session: dict = Depends(get_current_session),
    tenant_id: str | None = Depends(get_request_tenant_id),
    container: PlatformContainer = Depends(get_platform_container),
    resolver: DomainTenantResolver = Depends(get_domain_tenant_resolver),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Time-windowed sibling of `/metrics/dashboard` (last `hours` hours,
    not "since ever") — same tenant-scoping, same reasoning: looks up
    exactly the domains the caller's organization owns rather than ranking
    the whole platform and filtering down. Same admin/global option
    (Sprint 254) via `_resolve_metrics_scope()`.

    `hours` is clamped to [1, 720]: this is an authenticated-but-not-staff
    endpoint with no other per-request cost limit, and an unbounded window
    means an unbounded number of hourly Redis buckets read per domain —
    that cap applies just as much to an admin's global query, where it
    multiplies by every domain on the platform instead of one tenant's.
    """
    domains, scope, role = _resolve_metrics_scope(session, tenant_id, container, resolver)
    hours = max(1, min(hours, _MAX_WINDOW_HOURS))

    if scope == "global":
        _audit_global_access(container, session, tenant_id, role, "metrics.dashboard.window")

    if not domains:
        return {
            "items": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
            "window_hours": hours,
            "scope": scope,
        }

    items = store.domains_summary_window(domains, hours)

    items.sort(key=lambda item: (-item["total"], item["error_rate"] or 0, item["domain"]))

    total_items = len(items)
    paginated = items[offset : offset + limit]

    return {
        "items": paginated,
        "total": total_items,
        "limit": limit,
        "offset": offset,
        "window_hours": hours,
        "scope": scope,
    }


@router.get("/metrics/alerts")
async def get_metrics_alerts(
    background_tasks: BackgroundTasks,
    session: dict | None = Depends(get_optional_session),
    api_key_tenant: str | None = Depends(get_optional_api_key_tenant),
    tenant_id: str | None = Depends(get_request_tenant_id),
    container: PlatformContainer = Depends(get_platform_container),
    resolver: DomainTenantResolver = Depends(get_domain_tenant_resolver),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Same tenant-scoping as the other `/metrics/*` endpoints — only the
    caller's own domains are ever compared/flagged, unless `role == "admin"`
    (Sprint 254; see `_resolve_metrics_scope()`), in which case anomalies
    are detected/tracked across every domain on the platform.
    `store.detect_anomalies()` already returns alerts sorted by severity
    then impact (Sprint 251), so there's nothing left to sort here.

    `items`/`total` (not `alerts`/`count`, Sprint 250's original shape):
    aligned with `/metrics/dashboard` and `/metrics/dashboard/window`'s
    envelope now that all three `/metrics/*` list endpoints share the same
    tenant-scoped-list shape.

    `background_tasks` makes any newly-opened incident's webhook (Sprint
    252) fire after the response is sent, not inline during it — an
    unreachable/slow webhook endpoint must not add its own latency (up to
    the webhook client's own timeout) to this request.

    Response source (Sprint 253): when incident tracking is configured,
    reflects the authoritative, persisted active-incident state
    (`get_active_incidents()`) rather than just this one calculation — an
    ongoing incident stays visible even on a poll where, say, the domain
    list passed in happened to differ slightly. `detect_anomalies()` still
    always runs first regardless, for its side effects (opening/updating/
    resolving incidents, dispatching webhooks). Storages without incident
    tracking fall back to `detect_anomalies()`'s own returned list (Sprint
    251's debounce-based result) — `get_active_incidents()` would just be
    an empty no-op there, and silently returning that instead would erase
    this endpoint's only signal for those storages.

    `resolve_tenant=resolver.get_owner` (Sprint 258) lets each opened
    alert route through *its own domain's owning tenant's* configured
    alert channels, not just the caller's own tenant — required for the
    admin/global-scope case, where `domains` can span multiple tenants at
    once and a single flat tenant_id would misroute every domain that
    isn't the caller's own.

    `get_alert_limit` (Sprint 265) resolves each alert's rate-limit
    ceiling from that same owning tenant's plan (`PlatformAuth`'s
    already-established plan/limits system — see `platform_auth.py`),
    not a hardcoded default.

    Accepts an `X-API-Key` header in place of a session (Sprint 266,
    `_resolve_scope_with_api_key()`) — always `"tenant"` scope in that
    case, never `"global"`, regardless of the underlying organization's
    own admin status.
    """
    domains, scope, role = _resolve_scope_with_api_key(
        api_key_tenant, session, tenant_id, container, resolver
    )

    if scope == "global":
        _audit_global_access(container, session, tenant_id, role, "metrics.alerts")

    def get_alert_limit(alert_tenant_id: str) -> int:
        plan = container.auth().get_organization_plan(alert_tenant_id)
        return container.auth().get_plan_limits(plan).get("alerts_per_hour", 5)

    alerts = store.detect_anomalies(
        domains,
        resolve_tenant=resolver.get_owner,
        get_alert_limit=get_alert_limit,
        background_tasks=background_tasks,
    )

    items = store.get_active_incidents(domains) if store.has_incident_tracking() else alerts

    return {"items": items, "total": len(items), "scope": scope}


# Fetched before filtering/pagination, generous enough that a filtered
# page far from the start still sees the full matching set rather than
# being silently starved by an upstream fetch cap (see Sprint 264's
# get_metrics_incidents()/get_metrics_audit_log() docstrings) — bounded
# by IncidentManager's own history_limit (1000/domain) and PlatformAudit's
# own in-memory cap (10,000 events) either way, so this never actually
# forces either to read more than they already would.
_PAGINATION_FETCH_LIMIT = 10_000


def _apply_incident_filters(
    items: list[dict],
    severity: str | None,
    incident_type: str | None,
    domain: str | None,
) -> list[dict]:
    if severity:
        items = [item for item in items if item.get("severity") == severity]
    if incident_type:
        items = [item for item in items if item.get("type") == incident_type]
    if domain:
        items = [item for item in items if item.get("domain") == domain]

    return items


@router.get("/metrics/incidents/active")
async def get_metrics_incidents_active(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    severity: str | None = None,
    incident_type: str | None = None,
    domain: str | None = None,
    session: dict = Depends(get_current_session),
    tenant_id: str | None = Depends(get_request_tenant_id),
    container: PlatformContainer = Depends(get_platform_container),
    resolver: DomainTenantResolver = Depends(get_domain_tenant_resolver),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Same tenant-scoping as every other `/metrics/*` endpoint — only the
    caller's own domains' active incidents, never another tenant's, unless
    `role == "admin"` (Sprint 254).

    Paginated + filterable by `severity`/`incident_type`/`domain` (Sprint
    264) — `incident_type`, not the spec's own `type`: shadowing the
    `type` builtin as a parameter name works but is a real code smell,
    and this codebase already has an established name for this exact
    concept (`IncidentManager.open_or_update(domain, alert_type, ...)`,
    `_alert_type()`). The filtered field itself is still the incident
    record's own `"type"` key, unchanged.

    `items`/`total`/`scope` stay at the top level exactly as before
    (Sprint 253) — additive `meta` alongside them, not a replacement:
    every existing consumer/test reading `data["total"]`/`data["scope"]`
    keeps working unchanged, per this sprint's own "don't break existing
    endpoints" rule, which a wholesale envelope swap would have violated.
    """
    domains, scope, role = _resolve_metrics_scope(session, tenant_id, container, resolver)

    if scope == "global":
        _audit_global_access(container, session, tenant_id, role, "metrics.incidents.active")

    items = store.get_active_incidents(domains)
    items = _apply_incident_filters(items, severity, incident_type, domain)
    paginated = store.paginate(items, page, per_page)

    return {
        "items": paginated["items"],
        "total": paginated["meta"]["total"],
        "scope": scope,
        "meta": paginated["meta"],
    }


@router.get("/metrics/incidents")
async def get_metrics_incidents(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    severity: str | None = None,
    incident_type: str | None = None,
    domain: str | None = None,
    session: dict = Depends(get_current_session),
    tenant_id: str | None = Depends(get_request_tenant_id),
    container: PlatformContainer = Depends(get_platform_container),
    resolver: DomainTenantResolver = Depends(get_domain_tenant_resolver),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Same tenant-scoping as every other `/metrics/*` endpoint. Fixes a
    real cross-tenant leak in Sprint 252's own spec: it read a single flat,
    unscoped `incident:history` Redis list shared by every domain on the
    platform, and returned it to any authenticated caller with an
    organization — regardless of which domains they actually own. History
    is written and read per-domain (`IncidentManager`), scoped the same
    way `/metrics/dashboard` and `/metrics/alerts` already are, via
    `store.get_incident_history()` rather than reaching into
    `store._storage._client` directly (also present in that spec's own
    version — the same kind of encapsulation break already fixed for
    debounce, Sprint 251). `role == "admin"` (Sprint 254) sees history
    merged across every domain on the platform instead.

    Paginated + filterable (Sprint 264), same reasoning as
    `get_metrics_incidents_active()` above. The old `limit: int = 100`
    query param is gone, replaced by `page`/`per_page`; internally,
    `get_incident_history()` is now called with a generous
    `_PAGINATION_FETCH_LIMIT` rather than the old default — filtering and
    pagination both happen *after* the fetch, so a small fetch cap would
    silently starve any page beyond the first from ever seeing items
    that exist but were already truncated away upstream.
    """
    domains, scope, role = _resolve_metrics_scope(session, tenant_id, container, resolver)

    if scope == "global":
        _audit_global_access(container, session, tenant_id, role, "metrics.incidents")

    items = store.get_incident_history(domains, limit=_PAGINATION_FETCH_LIMIT)
    items = _apply_incident_filters(items, severity, incident_type, domain)
    paginated = store.paginate(items, page, per_page)

    return {
        "items": paginated["items"],
        "total": paginated["meta"]["total"],
        "scope": scope,
        "meta": paginated["meta"],
    }


@router.get("/metrics/audit")
async def get_metrics_audit_log(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
) -> dict:
    """Admin-only — unlike every other `/metrics/*` endpoint, this has no
    tenant-scoped fallback at all: it's a record of *admin behavior*
    (who read cross-tenant data, when), not tenant business data, so a
    regular user isn't entitled to a restricted slice of it either — they
    get a 403, not `{"items": [], "total": 0}`, matching the established
    `role != "admin"` gate already used by `/api/v1/metrics`, `/api/v1/logs`
    and `/api/v1/audit/events` (all pre-existing, unrelated routers) rather
    than the "empty is a valid state" convention used by the tenant-scoped
    `/metrics/*` endpoints above.

    Deliberately global, not filtered by the caller's own organization:
    each admin's own org (auto-created at registration) is essentially
    incidental to them — a compliance-facing "who accessed what, across
    the whole platform" log needs to stay unified regardless of which
    admin is looking at it, or it stops answering the question it exists
    to answer.

    Paginated (Sprint 264) — the old `limit: int = 50` query param is
    gone, replaced by `page`/`per_page`. Two real bugs in the spec's own
    version, fixed here:

    1. `container.audit.get_events()` with no `event=` filter — this
       endpoint has always shown only `metrics_global_access` events
       (Sprint 255's deliberate scope: admin cross-tenant *reads*, not
       every audit event this platform logs — registrations, logins,
       branding changes, ...). Dropping the filter would silently widen
       what this endpoint exposes to every event type ever logged, a
       real behavior regression even though it's still admin-gated.
    2. Calling `get_events()` with no `limit` relies on its own default
       (100) — filtering/pagination happen *after* the fetch, so a page
       beyond the first ~100 events would silently see nothing even if
       more genuinely exist. Fixed with the same generous
       `_PAGINATION_FETCH_LIMIT` used by `get_metrics_incidents()`,
       bounded by `PlatformAudit`'s own in-memory cap either way.

    `LoaderMetricsStore.paginate()` is called directly on the class
    (`@staticmethod`, no `store: LoaderMetricsStore = Depends(...)`
    needed) — this endpoint has nothing else to do with a
    `LoaderMetricsStore`, so adding that dependency just to reach a pure,
    stateless helper would be unnecessary coupling.
    """
    role = container.auth().get_user_role(session["email"])

    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")

    if container.audit is None:
        empty = LoaderMetricsStore.paginate([], page, per_page)
        return {"items": [], "total": 0, "meta": empty["meta"]}

    events = container.audit.get_events(
        event=_GLOBAL_ACCESS_AUDIT_EVENT, limit=_PAGINATION_FETCH_LIMIT
    )
    paginated = LoaderMetricsStore.paginate(events, page, per_page)

    return {
        "items": paginated["items"],
        "total": paginated["meta"]["total"],
        "meta": paginated["meta"],
    }


class SetWebhookRequest(BaseModel):
    url: str


def _require_admin(session: dict, container: PlatformContainer) -> str:
    """Returns the caller's role (always `"admin"` if this returns at all)
    so callers that need it for audit metadata (Sprint 257's
    `/metrics/webhook/metrics`) don't have to look it up a second time."""
    role = container.auth().get_user_role(session["email"])

    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")

    return role


@router.post("/metrics/webhook")
async def set_metrics_webhook(
    body: SetWebhookRequest,
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Admin-only (Sprint 256) — sets the outbound alert-webhook target at
    runtime, stored in `WebhookQueue`'s own Redis key, not a fixed
    `WEBHOOK_URL` env var read once at process start. `WebhookWorker`
    reads it fresh on every drain, so this takes effect immediately for
    already-queued and future alerts alike.

    A proper `SetWebhookRequest` JSON body, not a bare `url: str` query
    parameter (the spec's original snippet) — every other POST endpoint in
    this router/codebase (`RegisterRequest`, `SetBrandingRequest`, ...)
    takes a Pydantic body, and a URL in a query string is more likely to
    leak into access logs than one in a JSON body.

    503, not a crash, when no `webhook_queue` is configured (no Redis) —
    same "optional capability, no crash" convention as every other
    storage-dependent feature in this module.
    """
    _require_admin(session, container)

    if not store.set_webhook_url(body.url):
        raise HTTPException(status_code=503, detail="Webhook queue not configured")

    return {"ok": True}


@router.get("/metrics/webhook/status")
async def get_metrics_webhook_status(
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Admin-only (Sprint 256) — pending/dead-lettered delivery counts, not
    just `queue_size` (the spec's own version): a queue that's draining
    fine but silently accumulating dead-lettered items would look
    identical to a healthy one if `failed_count` weren't surfaced too,
    defeating this sprint's own "failures aren't invisible" goal.
    """
    _require_admin(session, container)

    return store.webhook_queue_status()


@router.post("/metrics/webhook/process")
async def process_metrics_webhook_queue(
    limit: int = 10,
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Admin-only, additive to the spec: manually drains up to `limit`
    pending webhook deliveries. Not in the original spec, but necessary —
    that spec never wired anything to actually call `WebhookWorker.process()`
    on an ongoing basis. `_send_webhook()` already schedules a drain via
    `BackgroundTasks` right after every new alert (best-effort, same-
    request-cycle delivery), which covers the common case; this endpoint
    is the manual/cron-triggerable fallback for anything still queued from
    an earlier failed attempt, or from before a webhook URL was ever
    configured — this codebase has no running job scheduler this queue
    could otherwise piggyback on (see webhook_queue.py's docstring on why
    this doesn't use the project's existing but unrelated Celery worker).
    """
    _require_admin(session, container)

    result = store.process_webhook_queue(limit)
    if result is None:
        raise HTTPException(status_code=503, detail="Webhook queue not configured")

    return result


_WEBHOOK_METRICS_AUDIT_EVENT = "metrics_webhook_metrics_access"


@router.get("/metrics/webhook/metrics")
async def get_metrics_webhook_metrics(
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Admin-only (Sprint 257) — delivery observability for the webhook
    queue: how many attempts, how many succeeded, how many are being
    retried, how many were ultimately dead-lettered. Same RBAC pattern as
    `/metrics/audit` (fresh `get_user_role()` lookup, 403 for non-admins,
    no tenant-scoped fallback — this is platform operational data, not
    tenant business data).

    Zeroed, not an error, when no `webhook_queue` is configured — same
    "optional capability, no crash" convention as `/metrics/webhook/status`.

    Every access is itself audited via `PlatformAudit`, under its own
    event name (`metrics_webhook_metrics_access`) rather than reusing
    Sprint 255's `metrics_global_access`: that event specifically marks a
    tenant-scoped endpoint being widened to cross-tenant/global for an
    admin (see `_audit_global_access()`), which doesn't describe this
    endpoint — there's no tenant-scoped variant of this data at all, only
    an admin-only one. `email` and `timestamp` aren't duplicated into the
    metadata dict: `PlatformAudit.log_event()` already records both as
    top-level fields on every event it logs.
    """
    role = _require_admin(session, container)

    if container.audit is not None:
        organization_id = container.auth().get_user_organization(session["email"])
        container.audit.log_event(
            _WEBHOOK_METRICS_AUDIT_EVENT,
            session["email"],
            organization_id,
            {"role": role},
        )

    return store.webhook_metrics()


class CreateChannelRequest(BaseModel):
    type: Literal["generic", "slack"]
    url: str
    severities: list[str] = []
    # Sprint 259: optional per-channel type filter (`error`/`latency`/...).
    # Omitted (`None`) means "matches every type", same as a channel with
    # no `severities` restricting nothing... except `severities` actually
    # defaults to `[]`, which matches *no* severity (deliberately strict);
    # `types` defaults to `None`, matching *every* type (deliberately
    # permissive) since this filter is new and optional — an existing
    # channel that never set it shouldn't suddenly stop receiving alerts.
    types: list[str] | None = None


@router.post("/metrics/webhook/channel")
async def create_alert_channel(
    body: CreateChannelRequest,
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Admin-only (Sprint 258), scoped to the calling admin's own
    organization — the original spec's own router code restricted all
    three channel endpoints to `role == "admin"` and derived `tenant_id`
    from the *caller's* own org, so that's what's implemented here; a
    self-serve version for non-admin tenant owners would be a separate,
    larger change (this endpoint's RBAC as specified means only a
    platform admin can configure channels, and only for their own org).

    `async def` + `Depends(get_metrics_store)` injected as a normal
    parameter, not the spec's own `def create_channel(...)` (sync) that
    called `get_metrics_store()` directly inside the body: calling it
    directly bypasses FastAPI's dependency-override mechanism entirely,
    so `app.dependency_overrides[get_metrics_store]` (used by every test
    in this whole test suite) would have no effect and every test would
    silently hit the real production singleton instead of its own
    injected store.

    A proper `CreateChannelRequest` body (with `type` constrained to the
    two channel types this sprint actually implements), not a bare
    `payload: dict` — an unvalidated dict would let `severities` be, say,
    a raw string instead of a list, which `AlertChannelManager.
    get_active_channels()`'s `severity in c.get("severities", [])` check
    would then silently misapply as substring containment instead of an
    exact-value membership test.

    503, not a crash, when the storage has no `channel_manager`
    configured (no Redis) — same "optional capability, no crash"
    convention as `/metrics/webhook`.
    """
    _require_admin(session, container)

    tenant_id = container.auth().get_user_organization(session["email"])

    # exclude_none: an omitted `types` shouldn't be stored as a literal
    # `null` key (kept out of the JSON blob entirely, matching
    # WebhookQueue.enqueue()'s own "only store a field when it applies"
    # convention) — cosmetic here since get_active_channels() already
    # treats a falsy `types` as "no filter" either way, but keeps stored
    # channel data free of redundant nulls.
    channel = store.add_alert_channel(tenant_id, body.model_dump(exclude_none=True))
    if channel is None:
        raise HTTPException(status_code=503, detail="Alert channels not configured")

    return channel


@router.get("/metrics/webhook/channel")
async def list_alert_channels(
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Admin-only, same scoping as `create_alert_channel()` — the calling
    admin's own organization's channels, not every tenant's."""
    _require_admin(session, container)

    tenant_id = container.auth().get_user_organization(session["email"])

    return {"items": store.get_alert_channels(tenant_id)}


@router.delete("/metrics/webhook/channel/{channel_id}")
async def delete_alert_channel(
    channel_id: str,
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Admin-only, same scoping as `create_alert_channel()`. Idempotent —
    deleting a channel_id that doesn't exist (already deleted, wrong id)
    still returns 200/"deleted" rather than 404, matching
    `AlertChannelManager.remove_channel()`'s own no-op-if-absent
    semantics; only a genuinely unconfigured `channel_manager` (no Redis)
    gets a 503.
    """
    _require_admin(session, container)

    tenant_id = container.auth().get_user_organization(session["email"])

    if not store.remove_alert_channel(tenant_id, channel_id):
        raise HTTPException(status_code=503, detail="Alert channels not configured")

    return {"status": "deleted"}


class SilenceAlertRequest(BaseModel):
    domain: str
    seconds: int = 3600


@router.post("/metrics/alerts/silence")
async def silence_alert(
    body: SilenceAlertRequest,
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Admin-only (Sprint 259). Fixes from the spec's own router code:

    1. `_require_admin(container, session)` — arguments swapped versus
       this helper's real signature (`_require_admin(session,
       container)`, Sprint 256). Called as written, `container.auth()`
       inside `_require_admin()` would run on the actual `session` dict
       (bound to the `container` parameter slot) — `dict` has no `.auth`
       attribute, an immediate `AttributeError`/500 on every call.
    2. A bare `payload: dict` with `payload["domain"]` — a missing key
       raises `KeyError` (uncaught, 500) instead of a clean 422. Fixed
       with a `SilenceAlertRequest` body.
    3. `getattr(store._storage, "alert_controls", None)` reached past
       `store` into its private `_storage` from the router — the same
       encapsulation break already fixed for channels/webhook queue.
       Fixed via `store.silence_alert()`.

    503 (not the spec's own `{"status": "not_supported"}`, a 200) when
    `alert_controls` isn't configured — matching the established
    "optional capability that can't perform a write" convention already
    used by `/metrics/webhook` and `/metrics/webhook/channel`, rather
    than introducing a third, inconsistent shape for the same situation.
    """
    _require_admin(session, container)

    if not store.silence_alert(body.domain, body.seconds):
        raise HTTPException(status_code=503, detail="Alert controls not configured")

    return {"status": "silenced"}


class UnsilenceAlertRequest(BaseModel):
    domain: str


@router.post("/metrics/alerts/unsilence")
async def unsilence_alert(
    body: UnsilenceAlertRequest,
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Admin-only. Fixes the same `_require_admin` argument-order bug as
    `silence_alert()`, plus `store._storage._client.delete(key)` — two
    levels of private-attribute reach-through from the router (past
    `store` *and* past `storage`) — replaced with `store.unsilence_alert()`.
    """
    _require_admin(session, container)

    if not store.unsilence_alert(body.domain):
        raise HTTPException(status_code=503, detail="Alert controls not configured")

    return {"status": "unsilenced"}


@router.get("/metrics/alerts/silenced")
async def list_silenced_alerts(
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Admin-only. Fixes `client.keys("alert:silenced:*")` — `KEYS` blocks
    the whole Redis instance for every other client while it walks the
    entire keyspace, the exact anti-pattern already fixed for
    `top_domains()` (Sprint 247); `AlertControlManager.list_silenced()`
    uses `scan_iter` instead. Also fixes the same `store._storage._client`
    reach-through as the other two endpoints here.

    Always 200 (`{"items": []}` when `alert_controls` isn't configured),
    not a 503 — a read, matching `GET /metrics/webhook/channel`'s own
    convention rather than the write endpoints' 503-on-missing-capability
    one.
    """
    _require_admin(session, container)

    return {"items": store.list_silenced_alerts()}


@router.post("/metrics/alerts/digest/flush")
async def flush_digest(
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Admin-only (Sprint 260). Fixes from the spec's own router code:

    1. `request: Request` + `session = request.state.session` — nothing
       in this app ever sets `request.state.session`; every endpoint in
       this router authenticates via `session: dict =
       Depends(get_current_session)` instead (the same
       `request.state.tenant_id`-style bug already fixed in Sprint 248).
       As written, this would raise `AttributeError` on every call.
    2. `resolver: DomainTenantResolver = Depends(get_tenant_resolver)` —
       `get_tenant_resolver` doesn't exist (the real dependency is
       `get_domain_tenant_resolver`), and the parameter was never even
       used in the endpoint body. Dropped rather than fixed-and-kept:
       nothing here needs it, `tenant_id` comes from the calling admin's
       own organization instead, same as the channel endpoints.
    3. `session.get("organization_id")` — works (that key is real on the
       session dict), but every other tenant-scoped endpoint added since
       Sprint 258 (`create_alert_channel()` and friends) uses a fresh
       `container.auth().get_user_organization(session["email"])` lookup
       instead of a value cached at login time. Matched here for
       consistency rather than introducing a third way to get "the
       calling admin's own org" in this same file.

    `{"items": [], "total": 0}` when the caller has no organization —
    matches this endpoint's own already-correct fallback shape from the
    spec.
    """
    _require_admin(session, container)

    tenant_id = container.auth().get_user_organization(session["email"])

    if not tenant_id:
        return {"items": [], "total": 0}

    items = store.flush_alert_digest(tenant_id)

    return {"items": items, "total": len(items)}


@router.get("/metrics/alerts/insights")
async def get_alert_insights(
    session: dict = Depends(get_current_session),
    tenant_id: str | None = Depends(get_request_tenant_id),
    container: PlatformContainer = Depends(get_platform_container),
    resolver: DomainTenantResolver = Depends(get_domain_tenant_resolver),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Top domains by alert count, severity distribution, and affected-
    domain count — same tenant-scoping as every other `/metrics/*`
    endpoint (Sprint 261), read-only over `get_active_incidents()`'s
    already-authoritative state; `detect_anomalies()` itself is untouched.

    Fixes from the spec's own router code:

    1. `_resolve_metrics_scope(session, resolver, container)` — wrong
       argument order *and* missing `tenant_id` entirely versus the real
       signature (`_resolve_metrics_scope(session, tenant_id, container,
       resolver)`, Sprint 254). Called as written, this raises
       `TypeError: missing 1 required positional argument: 'resolver'`
       on every call — `tenant_id` was never even declared as a
       dependency on this endpoint to begin with.
    2. No audit call for the `scope == "global"` case — every other
       `_resolve_metrics_scope()`-consuming endpoint (`/metrics/dashboard`,
       `/metrics/dashboard/window`, `/metrics/alerts`,
       `/metrics/incidents(/active)`) audits a cross-tenant admin read via
       `_audit_global_access()` (Sprint 255); an admin viewing insights
       across every tenant's incidents is exactly that kind of read, and
       skipping it here would leave a gap in the "who accessed cross-
       tenant data, when" compliance trail that subsystem exists for.
    """
    domains, scope, role = _resolve_metrics_scope(session, tenant_id, container, resolver)

    if scope == "global":
        _audit_global_access(container, session, tenant_id, role, "metrics.alerts.insights")

    data = store.get_alert_insights(domains)

    return {"scope": scope, "items": data}


@router.get("/metrics/alerts/digest")
async def get_alert_digest(
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Admin-only, read-only visibility into how many alerts are pending
    in the calling admin's own tenant digest, without flushing them
    (Sprint 261) — a lightweight companion to
    `POST /metrics/alerts/digest/flush` (Sprint 260).

    Fixes from the spec's own router code:

    1. `session.get("organization_id")` — same staleness inconsistency
       already fixed for `flush_digest()` (Sprint 260); matched to the
       same fresh `container.auth().get_user_organization(...)` lookup
       for consistency within this file.
    2. `getattr(store._storage, "alert_digest", None)` — reaches straight
       past `store` into its private `_storage`, the same encapsulation
       break already fixed for every other capability in this router
       since Sprint 251. Fixed via `store.get_digest_size()`.
    """
    _require_admin(session, container)

    tenant_id = container.auth().get_user_organization(session["email"])

    if not tenant_id:
        return {"items": [], "total": 0}

    size = store.get_digest_size(tenant_id)

    return {"items": [{"pending": size}], "total": 1 if size else 0}


@router.get("/metrics/dashboard/overview")
async def get_dashboard_overview(
    session: dict = Depends(get_current_session),
    tenant_id: str | None = Depends(get_request_tenant_id),
    container: PlatformContainer = Depends(get_platform_container),
    resolver: DomainTenantResolver = Depends(get_domain_tenant_resolver),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Unified dashboard aggregate (Sprint 262) — alert insights, pending
    digest count, platform traffic summary, and a business health score
    in one call, entirely through `LoaderMetricsStore.get_dashboard_data()`
    (no new aggregation logic here, no direct storage/Redis access).

    Fixes from the spec's own router code:

    1. `_resolve_metrics_scope(session, resolver, container)` — same
       wrong-argument-order-and-missing-`tenant_id` bug already fixed for
       `/metrics/alerts/insights` (Sprint 261) versus the real signature
       (`_resolve_metrics_scope(session, tenant_id, container,
       resolver)`, Sprint 254); `tenant_id` wasn't even declared as a
       dependency. `TypeError` on every call as written.
    2. `_audit_global_access(container, session, resource=...)` — missing
       2 of `_audit_global_access()`'s 5 required arguments (`tenant_id`,
       `role`); `TypeError` on every admin/global call. Fixed by passing
       all 5, matching every other caller of this helper since Sprint 255.
    3. The spec introduced a *second*, differently-purposed `tenant_id`
       local (`container.auth().get_user_organization(...)`, only in the
       `scope == "tenant"` branch) alongside the `tenant_id` dependency
       `_resolve_metrics_scope()` itself needs — two same-named values
       with different meanings in the same function. Reused the single
       `tenant_id` from `get_request_tenant_id` for both purposes
       instead: it's exactly the tenant whose domains
       `_resolve_metrics_scope()` resolved for the `"tenant"` branch, so
       it's also the right one to check a pending digest for; `None` in
       the `"global"` branch, where there's no single tenant's digest to
       report anyway.
    """
    domains, scope, role = _resolve_metrics_scope(session, tenant_id, container, resolver)

    if scope == "global":
        _audit_global_access(container, session, tenant_id, role, "metrics.dashboard.overview")

    digest_tenant_id = tenant_id if scope == "tenant" else None
    data = store.get_dashboard_data(domains, digest_tenant_id)

    return {"scope": scope, "items": data}


@router.get("/metrics/chart/{domain}")
async def get_metrics_chart(
    domain: str,
    session: dict | None = Depends(get_optional_session),
    api_key_tenant: str | None = Depends(get_optional_api_key_tenant),
    tenant_id: str | None = Depends(get_request_tenant_id),
    container: PlatformContainer = Depends(get_platform_container),
    resolver: DomainTenantResolver = Depends(get_domain_tenant_resolver),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Chart-ready 24h hourly time series for a single domain (Sprint
    263) — ownership-checked the same way `/metrics/summary`'s own
    `domain` filter is: a non-admin caller gets 403 for a domain outside
    their own tenant-scoped `domains`; an admin (`scope == "global"`)
    can query any domain. An API-key caller (Sprint 266) is always
    `"tenant"` scope, so this ownership check applies to it exactly the
    same way — a key can never chart a domain outside its own tenant.

    Fixes from the spec's own router code:

    1. `_resolve_metrics_scope(session, resolver, container)` — same
       wrong-argument-order-and-missing-`tenant_id` bug already fixed for
       `/metrics/alerts/insights` (Sprint 261) and
       `/metrics/dashboard/overview` (Sprint 262).
    2. No audit call for the `scope == "global"` case — every other
       `_resolve_metrics_scope()`-consuming endpoint since Sprint 255 has
       audited a cross-tenant admin read; an admin charting any tenant's
       domain traffic is exactly that. Added for consistency, matching
       the established pattern even though this sprint's own RULES
       didn't explicitly restate it.
    """
    domains, scope, role = _resolve_scope_with_api_key(
        api_key_tenant, session, tenant_id, container, resolver
    )

    if domain not in domains and scope != "global":
        raise HTTPException(status_code=403, detail="Domain not allowed")

    if scope == "global":
        _audit_global_access(container, session, tenant_id, role, "metrics.chart")

    data = store.get_time_series(domain)

    return {"domain": domain, "items": data}


@router.get("/metrics/incidents/top")
async def get_top_incidents(
    session: dict = Depends(get_current_session),
    tenant_id: str | None = Depends(get_request_tenant_id),
    container: PlatformContainer = Depends(get_platform_container),
    resolver: DomainTenantResolver = Depends(get_domain_tenant_resolver),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Up to 10 highest-priority active incidents (Sprint 263), same
    tenant-scoping and audit treatment as every other `/metrics/*`
    endpoint. Same `_resolve_metrics_scope()` argument-order fix as
    `get_metrics_chart()` above.
    """
    domains, scope, role = _resolve_metrics_scope(session, tenant_id, container, resolver)

    if scope == "global":
        _audit_global_access(container, session, tenant_id, role, "metrics.incidents.top")

    items = store.get_top_incidents(domains)

    return {"scope": scope, "items": items, "total": len(items)}


@router.get("/metrics/live-status")
async def get_live_status(
    session: dict | None = Depends(get_optional_session),
    api_key_tenant: str | None = Depends(get_optional_api_key_tenant),
    tenant_id: str | None = Depends(get_request_tenant_id),
    container: PlatformContainer = Depends(get_platform_container),
    resolver: DomainTenantResolver = Depends(get_domain_tenant_resolver),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> dict:
    """Per-domain live status (`healthy`/`degraded`/`critical`, Sprint
    263), same tenant-scoping and audit treatment as every other
    `/metrics/*` endpoint. Same `_resolve_metrics_scope()` argument-order
    fix as `get_metrics_chart()` above. Accepts an `X-API-Key` header in
    place of a session (Sprint 266) — see `_resolve_scope_with_api_key()`.
    """
    domains, scope, role = _resolve_scope_with_api_key(
        api_key_tenant, session, tenant_id, container, resolver
    )

    if scope == "global":
        _audit_global_access(container, session, tenant_id, role, "metrics.live_status")

    items = store.get_live_status(domains)

    return {"scope": scope, "items": items}
