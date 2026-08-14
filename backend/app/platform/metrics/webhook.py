import json
import urllib.request


class WebhookClient:
    """Fire-and-forget outbound webhook (Slack-compatible: any endpoint
    that accepts a JSON POST body works). Never raises — a misconfigured or
    unreachable webhook URL must not break anomaly detection or the request
    that triggered it. Callers on the request path should still prefer
    scheduling `send()` via `BackgroundTasks` (see
    `LoaderMetricsStore._send_webhook()`) rather than calling it inline:
    this class's own timeout only bounds how long the underlying socket
    call can block *once started*, it doesn't make the call non-blocking.
    """

    def __init__(self, url: str, timeout_seconds: float = 2.0):
        self._url = url
        self._timeout = timeout_seconds

    def send(self, payload: dict) -> bool:
        """Returns whether the POST actually succeeded (2xx) — `False`,
        never a raised exception, on any failure (unreachable host,
        connection timeout, or an HTTP error status; `urlopen` itself
        already raises `HTTPError` for a non-2xx response, so no explicit
        status check is needed beyond catching it like every other
        failure here). `WebhookWorker` (Sprint 256) uses this to decide
        whether to retry; the original Sprint 252 callers that ignore the
        return value are unaffected.
        """
        try:
            request = urllib.request.Request(
                self._url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(request, timeout=self._timeout)
            return True
        except Exception:
            return False
