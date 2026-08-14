import logging

from app.platform.metrics.webhook import WebhookClient

logger = logging.getLogger("app.platform.metrics.webhook_worker")


class WebhookWorker:
    """Drains a `WebhookQueue` and attempts delivery of each item —
    "simple worker, no threads" (this sprint's own stated constraint): a
    plain synchronous `process()` method, invoked either via FastAPI
    `BackgroundTasks` right after an alert is enqueued (best-effort,
    same-request-cycle delivery, mirroring Sprint 252's non-blocking
    webhook dispatch) or via the admin-only `POST /metrics/webhook/process`
    endpoint (for whatever's still queued from an earlier failed attempt,
    or from before a worker/admin-URL was ever configured) — no polling
    loop, no persistent thread.

    Sends via `WebhookClient` (Sprint 252's already-tested stdlib-based
    HTTP client, extended to report success/failure), not the `requests`
    library the original spec proposed: `requests` isn't a dependency of
    this project (see requirements.txt), and `WebhookClient` already does
    exactly what's needed here without adding one.

    Each item's own `url` (Sprint 258, set at `enqueue()` time — e.g. one
    per alert channel) takes priority over the queue's shared
    `get_url()`/`set_url()` target; the shared target is only a fallback
    for items enqueued the Sprint 256 way, with no per-item url of their
    own.
    """

    def __init__(self, queue, timeout_seconds: float = 2.0, client_factory=WebhookClient):
        self._queue = queue
        self._timeout = timeout_seconds
        # Injectable, like `MetricsStorage` into `LoaderMetricsStore` — lets
        # tests exercise real retry/dead-letter behavior against a fake
        # client instead of doing actual network I/O to prove success vs.
        # failure paths.
        self._client_factory = client_factory

    def process(self, limit: int = 10) -> dict:
        default_url = self._queue.get_url()
        items = self._queue.dequeue_batch(limit)

        sent = 0
        failed = 0
        processed = 0

        for item in items:
            url = item.get("url") or default_url

            # No per-item target and no shared default configured yet:
            # put it back untouched rather than dequeuing-then-requeuing
            # it — that would burn through its retry budget for a
            # configuration gap, not an actual delivery failure, and
            # could dead-letter it before a target is ever configured.
            # Not counted in `processed`: nothing was actually attempted.
            if not url:
                self._queue.put_back(item)
                continue

            processed += 1
            client = self._client_factory(url, timeout_seconds=self._timeout)

            if client.send(item["payload"]):
                # Recorded only after confirmed delivery — never
                # speculatively before `send()` returns, and never for an
                # attempt that's about to be retried instead (Sprint 257).
                self._queue.record_success()
                sent += 1
            else:
                logger.warning(
                    "Webhook delivery failed (retry %s so far): %s",
                    item.get("retries", 0),
                    url,
                )
                # Recorded before requeue(): every failed attempt counts
                # as a retry here, whether requeue() ends up actually
                # requeuing it or immediately dead-lettering it (which
                # separately bumps its own "failed" counter in that case).
                self._queue.record_retry()
                self._queue.requeue(item)
                failed += 1

        return {"sent": sent, "failed": failed, "processed": processed}
