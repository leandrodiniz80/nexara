import logging
import os

from app.platform.metrics.alert_channels import AlertChannelManager
from app.platform.metrics.alert_controls import AlertControlManager
from app.platform.metrics.alert_digest import AlertDigestManager
from app.platform.metrics.alert_rate_limiter import AlertRateLimiter
from app.platform.metrics.incident_manager import IncidentManager
from app.platform.metrics.loader_metrics import LoaderMetricsStore
from app.platform.metrics.metrics_storage import (
    AggregatedRedisMetricsStorage,
    InMemoryMetricsStorage,
    MetricsStorage,
)
from app.platform.metrics.webhook import WebhookClient
from app.platform.metrics.webhook_queue import WebhookQueue
from app.platform.metrics.webhook_worker import WebhookWorker
from app.platform.usage.usage_tracker import UsageTracker

logger = logging.getLogger("app.api.metrics")

_metrics_store: LoaderMetricsStore | None = None

# Real Redis client construction is deliberately import-guarded and lazy
# (only attempted inside _create_storage(), never at module import time):
# `redis` is a hard dependency of this project either way, but a process
# that never sets REDIS_URL should never even try to open a connection.
_CONNECT_TIMEOUT_SECONDS = 2


def _create_storage() -> MetricsStorage:
    redis_url = os.getenv("REDIS_URL")

    if not redis_url:
        return InMemoryMetricsStorage()

    try:
        import redis

        client = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=_CONNECT_TIMEOUT_SECONDS,
            socket_timeout=_CONNECT_TIMEOUT_SECONDS,
        )
        client.ping()

        webhook = None
        webhook_url = os.getenv("WEBHOOK_URL")
        if webhook_url:
            webhook = WebhookClient(webhook_url)

        # webhook_queue/webhook_worker (Sprint 256) are always wired up
        # once Redis is available, independent of WEBHOOK_URL: that's what
        # lets an admin configure/change the delivery target at runtime via
        # POST /metrics/webhook, seeded here from WEBHOOK_URL if it's set
        # so existing env-var-based deployments keep working unchanged.
        # `_send_webhook()` prefers this queue+retry path over the plain
        # `webhook` above whenever it's present.
        webhook_queue = WebhookQueue(client)
        if webhook_url:
            webhook_queue.set_url(webhook_url)
        webhook_worker = WebhookWorker(webhook_queue)

        # channel_manager (Sprint 258) needs nothing beyond the same
        # client, same reasoning as incident_manager — always available
        # once Redis is, whether or not any tenant has configured a
        # channel yet.
        channel_manager = AlertChannelManager(client)

        # alert_controls (Sprint 259) needs nothing beyond the same client
        # either — same reasoning as channel_manager/incident_manager.
        alert_controls = AlertControlManager(client)

        # alert_digest/rate_limiter (Sprint 260) need nothing beyond the
        # same client either.
        alert_digest = AlertDigestManager(client)
        rate_limiter = AlertRateLimiter(client)

        # usage_tracker (Sprint 270) needs nothing beyond the same client
        # either.
        usage_tracker = UsageTracker(client)

        # Aggregated (O(1) counters), not the raw-list RedisMetricsStorage:
        # /cdn/metrics/summary is the only consumer of Redis-backed storage
        # in this app, and a scanned list gets slower on every read as it
        # grows under real traffic — counters don't. incident_manager and
        # webhook are optional capabilities (Sprint 252): webhook stays
        # None (never sent) unless WEBHOOK_URL is actually configured;
        # incident tracking is always available once Redis is, since it
        # needs nothing beyond the same client.
        return AggregatedRedisMetricsStorage(
            client,
            incident_manager=IncidentManager(client),
            webhook=webhook,
            webhook_queue=webhook_queue,
            webhook_worker=webhook_worker,
            channel_manager=channel_manager,
            alert_controls=alert_controls,
            alert_digest=alert_digest,
            rate_limiter=rate_limiter,
            usage_tracker=usage_tracker,
        )
    except Exception:
        # REDIS_URL was set but the connection failed (down, wrong
        # credentials, network partition, ...): fall back to in-memory
        # rather than taking the whole app down, but this is loud, not
        # silent — an operator who believes metrics are being persisted to
        # Redis needs to see this in the logs, not discover it by noticing
        # data missing after a restart.
        logger.warning("REDIS_URL is set but Redis is unreachable; falling back to in-memory")
        return InMemoryMetricsStorage()


def get_metrics_store() -> LoaderMetricsStore:
    """Storage is Redis-backed when `REDIS_URL` is set and reachable at
    first use, in-memory otherwise (unset, or Redis unreachable) — either
    way, nothing else in the app depends on which `MetricsStorage` is
    behind `LoaderMetricsStore`. Without Redis actually configured and
    reachable, events still do NOT survive a process restart.
    """
    global _metrics_store

    if _metrics_store is None:
        _metrics_store = LoaderMetricsStore(storage=_create_storage())

    return _metrics_store
