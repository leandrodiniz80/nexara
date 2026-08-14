import logging

from fastapi import Depends

from app.api.dependencies.auth import get_platform_container
from app.api.dependencies.metrics import get_metrics_store
from app.core.config import settings
from app.platform.billing.billing_analytics import BillingAnalytics
from app.platform.billing.billing_metrics import BillingMetrics
from app.platform.billing.decision_engine import BillingDecisionEngine
from app.platform.billing.processed_events_store import ProcessedStripeEventStore
from app.platform.billing.stripe_service import StripeService
from app.platform.billing.stripe_sync import StripeSyncService
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.metrics.loader_metrics import LoaderMetricsStore
from app.platform.notifications.notification_service import NotificationService
from app.platform.revenue.business_overview import BusinessOverviewEngine
from app.platform.revenue.lead_execution import LeadExecutionTracker
from app.platform.revenue.revenue_activation import RevenueActivationEngine
from app.platform.revenue.sales_playbook import SalesPlaybookEngine

logger = logging.getLogger("app.api.billing")

_stripe_service: StripeService | None = None
_action_store: ProcessedStripeEventStore | None = None
_CONNECT_TIMEOUT_SECONDS = 2
# Sprint 279. Deliberately much shorter than the webhook-dedup store's
# 30-day TTL right below — that TTL is sized for Stripe's own webhook
# retry window, which has nothing to do with how long an *outbound*
# decision-engine action should stay deduplicated. Long enough to absorb
# an accidental double-submit (a double-click, a client retry after a
# slow response); short enough that a legitimate later action (a
# customer who churns and re-subscribes weeks apart) is never silently
# blocked by a stale entry.
_ACTION_IDEMPOTENCY_TTL_SECONDS = 300


def _create_event_store():
    """Sprint 269: persistent (Redis-backed) webhook-idempotency store,
    replacing `StripeService`'s own in-memory `set()` fallback whenever
    Redis is actually reachable. Uses `settings.REDIS_URL` (this file's
    own established `settings.*` convention, unlike `app/api/
    dependencies/metrics.py`/`api_keys.py`, which read `os.getenv(
    "REDIS_URL")` directly) — `REDIS_URL` has no default in `Settings`,
    so it's always present once the app has started at all; the
    connection itself can still fail at runtime, which is what this
    still guards against with a graceful fallback to `None` (letting
    `StripeService` use its own in-memory set instead of raising).
    """
    try:
        import redis

        client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=_CONNECT_TIMEOUT_SECONDS,
            socket_timeout=_CONNECT_TIMEOUT_SECONDS,
        )
        client.ping()

        return ProcessedStripeEventStore(client)
    except Exception:
        logger.warning(
            "Redis unreachable; Stripe webhook idempotency falls back to "
            "an in-memory, per-process set"
        )
        return None


def _create_action_store() -> ProcessedStripeEventStore | None:
    """Sprint 279. A *separate* `ProcessedStripeEventStore` instance (own
    Redis connection, own short TTL) from the webhook-dedup one above —
    reuses the class (this sprint's own explicit "reutilizar
    ProcessedStripeEventStore" instruction), not the webhook instance
    itself or its 30-day TTL, which is sized for an unrelated purpose
    (see `_ACTION_IDEMPOTENCY_TTL_SECONDS`'s own comment). Guards
    `StripeSyncService`'s outbound actions against rapid duplicate
    invocation; `None` (Redis unreachable) disables only that app-level
    guard, not the per-call Stripe idempotency key `StripeSyncService`
    always sends regardless.
    """
    try:
        import redis

        client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=_CONNECT_TIMEOUT_SECONDS,
            socket_timeout=_CONNECT_TIMEOUT_SECONDS,
        )
        client.ping()

        return ProcessedStripeEventStore(client, ttl_seconds=_ACTION_IDEMPOTENCY_TTL_SECONDS)
    except Exception:
        logger.warning(
            "Redis unreachable; billing decision-engine action idempotency guard disabled"
        )
        return None


if settings.STRIPE_SECRET_KEY and settings.STRIPE_WEBHOOK_SECRET:
    _stripe_service = StripeService(
        secret_key=settings.STRIPE_SECRET_KEY,
        webhook_secret=settings.STRIPE_WEBHOOK_SECRET,
        price_ids={
            "pro": settings.STRIPE_PRICE_ID_PRO,
            "enterprise": settings.STRIPE_PRICE_ID_ENTERPRISE,
        },
        success_url=settings.STRIPE_SUCCESS_URL,
        cancel_url=settings.STRIPE_CANCEL_URL,
        event_store=_create_event_store(),
    )
    _action_store = _create_action_store()


def get_stripe_service() -> StripeService | None:
    """None when STRIPE_SECRET_KEY/STRIPE_WEBHOOK_SECRET aren't set — the feature
    toggle. Routes must treat that as "fall back to the manual upgrade flow", never
    as an error.
    """
    return _stripe_service


def get_stripe_sync_service(
    container: PlatformContainer = Depends(get_platform_container),
) -> StripeSyncService | None:
    """Sprint 279. `None` exactly when `get_stripe_service()` is (same
    feature-toggle shape) — `BillingDecisionEngine` must treat a `None`
    here as "can't safely act on any Stripe-bound organization", never
    as license to fall back to a direct plan mutation. Built fresh per
    request (cheap — just wraps the already-built singleton `_stripe_
    service`/`_action_store` with this request's own `container.auth()`)
    the same way `get_billing_analytics()`/`get_billing_metrics()`
    already are.
    """
    stripe_service = get_stripe_service()

    if stripe_service is None:
        return None

    return StripeSyncService(stripe_service, container.auth(), action_store=_action_store)


def get_billing_metrics(
    container: PlatformContainer = Depends(get_platform_container),
) -> BillingMetrics:
    """Sprint 272. The spec's own version, `get_billing_metrics(container)`,
    took a plain `container` argument with no `Depends()` default — not
    actually composable as a FastAPI dependency, since FastAPI resolves a
    sub-dependency's own parameters the same way it resolves a route's.
    Wired through `get_platform_container` (this file's own established
    pattern from `get_stripe_service`/`_create_event_store`) so the router
    can just declare `Depends(get_billing_metrics)`.
    """
    return BillingMetrics(container.auth())


def get_billing_analytics(
    container: PlatformContainer = Depends(get_platform_container),
    store: LoaderMetricsStore = Depends(get_metrics_store),
) -> BillingAnalytics:
    """Sprint 277's `upgrade_recommendations()` needs each organization's
    `alerts_sent` usage to flag high-usage free-plan orgs. `BillingAnalytics`
    only ever had `auth` before now — rather than give it a hard dependency
    on the whole `LoaderMetricsStore` (a bigger, unrelated object it would
    otherwise need to import and hold onto), it takes a plain `get_usage`
    callable instead, the same "inject a callable, not a dependency" shape
    already established for `resolve_tenant`/`get_alert_limit` (Sprint
    258/265) and `UsageAlerts` (Sprint 271). `store.get_usage` already
    degrades gracefully (returns 0) when no usage tracker is configured, so
    `BillingAnalytics` needs no additional fallback of its own for that case.
    """
    return BillingAnalytics(container.auth(), get_usage=store.get_usage)


def get_notification_service() -> NotificationService:
    """Sprint 281. No dependencies of its own yet (the stub doesn't talk
    to anything real), so a fresh instance per request is simplest —
    nothing here needs the singleton treatment `_stripe_service`/
    `_action_store` get, since there's no connection or shared state to
    reuse.
    """
    return NotificationService()


def get_decision_engine(
    container: PlatformContainer = Depends(get_platform_container),
    analytics: BillingAnalytics = Depends(get_billing_analytics),
    stripe_sync: StripeSyncService | None = Depends(get_stripe_sync_service),
    notifier: NotificationService = Depends(get_notification_service),
) -> BillingDecisionEngine:
    """Sprint 278. Reuses `get_billing_analytics`/`get_platform_container`
    exactly as that sprint's own spec asked, rather than reconstructing
    `container.auth()` access from scratch. Sprint 279 adds `stripe_sync`
    (`None` when Stripe isn't configured — `BillingDecisionEngine` itself
    already handles that gracefully, see its own docstring). Sprint 281
    adds `notifier` (never `None` here, unlike `stripe_sync` — the stub
    itself has no "unconfigured" state to represent).
    """
    return BillingDecisionEngine(
        analytics, container.auth(), stripe_sync=stripe_sync, notifier=notifier
    )


def get_revenue_activation_engine(
    analytics: BillingAnalytics = Depends(get_billing_analytics),
) -> RevenueActivationEngine:
    """Sprint 283. Reuses `get_billing_analytics` per this sprint's own
    spec — `RevenueActivationEngine` needs nothing else (see its own
    module docstring for why it doesn't take `auth` separately).
    """
    return RevenueActivationEngine(analytics)


def get_lead_execution_tracker(
    container: PlatformContainer = Depends(get_platform_container),
) -> LeadExecutionTracker:
    """Sprint 285. Built fresh per request — cheap, just wraps this
    request's own `container.auth()`, the same way `get_stripe_sync_
    service()`/`get_billing_metrics()` already do.
    """
    return LeadExecutionTracker(container.auth())


def get_sales_playbook_engine(
    activation_engine: RevenueActivationEngine = Depends(get_revenue_activation_engine),
    lead_tracker: LeadExecutionTracker = Depends(get_lead_execution_tracker),
) -> SalesPlaybookEngine:
    """Sprint 284. Reuses `get_revenue_activation_engine` per that
    sprint's own spec, rather than reconstructing a second
    `RevenueActivationEngine` from scratch. Sprint 285 adds
    `lead_tracker` so generated playbook entries carry each lead's
    current execution state (see `SalesPlaybookEngine`'s own docstring).
    """
    return SalesPlaybookEngine(activation_engine, lead_state_tracker=lead_tracker)


def get_business_overview_engine(
    analytics: BillingAnalytics = Depends(get_billing_analytics),
    activation_engine: RevenueActivationEngine = Depends(get_revenue_activation_engine),
    lead_tracker: LeadExecutionTracker = Depends(get_lead_execution_tracker),
) -> BusinessOverviewEngine:
    """Sprint 286. Reuses all three existing dependencies rather than
    reconstructing any of `BillingAnalytics`/`RevenueActivationEngine`/
    `LeadExecutionTracker` from scratch — this sprint's own explicit
    "não criar nova inteligência" rule extends to the DI wiring too.
    """
    return BusinessOverviewEngine(analytics, activation_engine, lead_tracker)
