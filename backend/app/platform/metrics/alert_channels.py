import json
import uuid


class AlertChannelManager:
    """Per-tenant list of alert delivery destinations (Sprint 258) —
    Redis-backed, one JSON list per tenant (`webhook:channels:{tenant_id}`),
    the same "one key holding a JSON blob" approach `WebhookQueue` already
    uses for its own `webhook:url` key.

    Not an optional-capability class accessed via a private attribute
    reach-through (`store._channel_manager`, as the original spec's router
    code did): `LoaderMetricsStore` exposes it through
    `add_alert_channel()`/`get_alert_channels()`/`remove_alert_channel()`,
    the same public-delegation pattern already used for
    `webhook_queue`/`webhook_worker` (`set_webhook_url()`,
    `process_webhook_queue()`, ...).
    """

    def __init__(self, client):
        self._client = client

    def _key(self, tenant_id: str) -> str:
        return f"webhook:channels:{tenant_id}"

    def add_channel(self, tenant_id: str, channel: dict) -> dict:
        channels = self.get_channels(tenant_id)

        channel = {**channel, "id": str(uuid.uuid4()), "enabled": True}
        channels.append(channel)

        self._client.set(self._key(tenant_id), json.dumps(channels))

        return channel

    def get_channels(self, tenant_id: str) -> list[dict]:
        raw = self._client.get(self._key(tenant_id))
        return json.loads(raw) if raw else []

    def remove_channel(self, tenant_id: str, channel_id: str) -> None:
        channels = self.get_channels(tenant_id)
        channels = [c for c in channels if c["id"] != channel_id]

        self._client.set(self._key(tenant_id), json.dumps(channels))

    def get_active_channels(
        self, tenant_id: str, severity: str, alert_type: str | None = None
    ) -> list[dict]:
        """`alert_type` (Sprint 259) is optional and additive: a channel
        with no `"types"` key configured (every channel created before
        this sprint, and any new one that doesn't set it) matches every
        type, unchanged from Sprint 258's behavior. A channel that *does*
        configure `"types"` only matches when `alert_type` is one of them
        — including correctly excluding it when the caller passes no
        `alert_type` at all, rather than crashing.
        """
        results = []

        for c in self.get_channels(tenant_id):
            if not c.get("enabled"):
                continue
            if severity not in c.get("severities", []):
                continue
            if c.get("types") and alert_type not in c["types"]:
                continue

            results.append(c)

        return results
