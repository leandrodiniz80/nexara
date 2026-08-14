"""Tests for AlertChannelManager (Sprint 258)."""

import json

from app.platform.metrics.alert_channels import AlertChannelManager


class _FakeRedisClient:
    def __init__(self):
        self._strings: dict[str, str] = {}

    def get(self, key):
        return self._strings.get(key)

    def set(self, key, value, nx=False, ex=None):
        self._strings[key] = value
        return True


def test_get_channels_vazio_por_padrao():
    manager = AlertChannelManager(_FakeRedisClient())

    assert manager.get_channels("tenant-a") == []


def test_add_channel_atribui_id_e_enabled():
    manager = AlertChannelManager(_FakeRedisClient())

    channel = manager.add_channel(
        "tenant-a", {"type": "slack", "url": "https://hooks.slack.com/x", "severities": ["high"]}
    )

    assert channel["id"]
    assert channel["enabled"] is True
    assert channel["type"] == "slack"


def test_add_channel_nao_muta_o_dict_original_do_chamador():
    manager = AlertChannelManager(_FakeRedisClient())
    original = {"type": "generic", "url": "https://example.com", "severities": []}

    manager.add_channel("tenant-a", original)

    assert "id" not in original
    assert "enabled" not in original


def test_add_channel_persiste_e_aparece_em_get_channels():
    manager = AlertChannelManager(_FakeRedisClient())
    manager.add_channel(
        "tenant-a", {"type": "generic", "url": "https://a.example.com", "severities": ["low"]}
    )

    channels = manager.get_channels("tenant-a")

    assert len(channels) == 1
    assert channels[0]["url"] == "https://a.example.com"


def test_channels_sao_isolados_por_tenant():
    manager = AlertChannelManager(_FakeRedisClient())
    manager.add_channel("tenant-a", {"type": "generic", "url": "https://a.example.com"})
    manager.add_channel("tenant-b", {"type": "generic", "url": "https://b.example.com"})

    assert len(manager.get_channels("tenant-a")) == 1
    assert len(manager.get_channels("tenant-b")) == 1
    assert manager.get_channels("tenant-a")[0]["url"] != manager.get_channels("tenant-b")[0]["url"]


def test_remove_channel_remove_pelo_id():
    manager = AlertChannelManager(_FakeRedisClient())
    channel = manager.add_channel("tenant-a", {"type": "generic", "url": "https://a.example.com"})

    manager.remove_channel("tenant-a", channel["id"])

    assert manager.get_channels("tenant-a") == []


def test_remove_channel_inexistente_nao_lanca_erro():
    manager = AlertChannelManager(_FakeRedisClient())
    manager.add_channel("tenant-a", {"type": "generic", "url": "https://a.example.com"})

    manager.remove_channel("tenant-a", "nao-existe")

    assert len(manager.get_channels("tenant-a")) == 1


def test_get_active_channels_filtra_por_severidade():
    manager = AlertChannelManager(_FakeRedisClient())
    manager.add_channel(
        "tenant-a",
        {"type": "slack", "url": "https://critical.example.com", "severities": ["critical"]},
    )
    manager.add_channel(
        "tenant-a", {"type": "generic", "url": "https://low.example.com", "severities": ["low"]}
    )

    active = manager.get_active_channels("tenant-a", "critical")

    assert len(active) == 1
    assert active[0]["url"] == "https://critical.example.com"


def test_get_active_channels_ignora_canal_desabilitado():
    client = _FakeRedisClient()
    manager = AlertChannelManager(client)
    manager.add_channel(
        "tenant-a", {"type": "slack", "url": "https://x.example.com", "severities": ["critical"]}
    )
    channels = manager.get_channels("tenant-a")
    channels[0]["enabled"] = False
    client.set("webhook:channels:tenant-a", json.dumps(channels))

    assert manager.get_active_channels("tenant-a", "critical") == []


def test_get_active_channels_vazio_para_tenant_sem_canais():
    manager = AlertChannelManager(_FakeRedisClient())

    assert manager.get_active_channels("tenant-a", "critical") == []


# --- Sprint 259: optional per-channel type filter -----------------------


def test_get_active_channels_sem_types_configurado_aceita_qualquer_tipo():
    """A channel with no `types` key (every channel created before Sprint
    259, and any new one that doesn't set it) must keep matching every
    alert type, unchanged from Sprint 258's behavior."""
    manager = AlertChannelManager(_FakeRedisClient())
    manager.add_channel(
        "tenant-a", {"type": "slack", "url": "https://x.example.com", "severities": ["critical"]}
    )

    active = manager.get_active_channels("tenant-a", "critical", alert_type="latency")

    assert len(active) == 1


def test_get_active_channels_filtra_por_tipo_quando_configurado():
    manager = AlertChannelManager(_FakeRedisClient())
    manager.add_channel(
        "tenant-a",
        {
            "type": "slack",
            "url": "https://errors-only.example.com",
            "severities": ["critical"],
            "types": ["error"],
        },
    )

    matching = manager.get_active_channels("tenant-a", "critical", alert_type="error")
    not_matching = manager.get_active_channels("tenant-a", "critical", alert_type="latency")

    assert len(matching) == 1
    assert not_matching == []


def test_get_active_channels_com_types_configurado_e_alert_type_ausente_nao_bate():
    """Calling without an alert_type against a type-filtered channel must
    exclude it (safe default), not raise or match unconditionally."""
    manager = AlertChannelManager(_FakeRedisClient())
    manager.add_channel(
        "tenant-a",
        {
            "type": "slack",
            "url": "https://x.example.com",
            "severities": ["critical"],
            "types": ["error"],
        },
    )

    assert manager.get_active_channels("tenant-a", "critical") == []
