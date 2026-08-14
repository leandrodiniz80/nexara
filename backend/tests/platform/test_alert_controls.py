"""Tests for AlertControlManager (Sprint 259: manual silencing + cooldown
anti-spam layer in front of _send_webhook()'s delivery mechanisms).
"""

import time

from app.platform.metrics.alert_controls import AlertControlManager


class _FakeRedisClient:
    def __init__(self):
        self._strings: dict[str, str] = {}

    def get(self, key):
        return self._strings.get(key)

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self._strings:
            return None

        self._strings[key] = str(value)
        return True

    def delete(self, key):
        self._strings.pop(key, None)

    def scan_iter(self, match=None):
        prefix = match.rstrip("*") if match else ""
        return [k for k in self._strings if k.startswith(prefix)]


def test_is_silenced_false_por_padrao():
    controls = AlertControlManager(_FakeRedisClient())

    assert controls.is_silenced("a.com") is False


def test_silence_torna_is_silenced_verdadeiro():
    controls = AlertControlManager(_FakeRedisClient())

    controls.silence("a.com", 3600)

    assert controls.is_silenced("a.com") is True


def test_is_silenced_expira_apos_o_tempo():
    """is_silenced() must key off the stored expiry *value*, not rely on
    the backing store's own TTL precision — provable here by seeding an
    already-past expiry timestamp directly, without needing a real sleep."""
    client = _FakeRedisClient()
    controls = AlertControlManager(client)
    past_expiry = int(time.time()) - 10
    client._strings[controls._silence_key("a.com")] = str(past_expiry)

    assert controls.is_silenced("a.com") is False


def test_silence_e_isolado_por_dominio():
    controls = AlertControlManager(_FakeRedisClient())

    controls.silence("a.com", 3600)

    assert controls.is_silenced("a.com") is True
    assert controls.is_silenced("b.com") is False


def test_unsilence_remove_o_silenciamento():
    controls = AlertControlManager(_FakeRedisClient())
    controls.silence("a.com", 3600)

    controls.unsilence("a.com")

    assert controls.is_silenced("a.com") is False


def test_unsilence_de_dominio_nao_silenciado_nao_lanca_erro():
    controls = AlertControlManager(_FakeRedisClient())

    controls.unsilence("never-silenced.com")

    assert controls.is_silenced("never-silenced.com") is False


def test_list_silenced_vazio_por_padrao():
    controls = AlertControlManager(_FakeRedisClient())

    assert controls.list_silenced() == []


def test_list_silenced_retorna_dominios_ativos():
    controls = AlertControlManager(_FakeRedisClient())
    controls.silence("a.com", 3600)
    controls.silence("b.com", 3600)

    assert sorted(controls.list_silenced()) == ["a.com", "b.com"]


def test_list_silenced_exclui_entradas_logicamente_expiradas():
    """Even if a stale key is still physically present (SCAN would still
    find it — the fake client here never really expires anything), an
    expired silence must not be reported as active: list_silenced()
    re-checks is_silenced() per match rather than trusting SCAN alone."""
    client = _FakeRedisClient()
    controls = AlertControlManager(client)
    controls.silence("active.com", 3600)
    client._strings[controls._silence_key("expired.com")] = str(int(time.time()) - 10)

    assert controls.list_silenced() == ["active.com"]


def test_allow_alert_primeira_vez_permite():
    controls = AlertControlManager(_FakeRedisClient())

    assert controls.allow_alert("a.com", "error", cooldown=300) is True


def test_allow_alert_bloqueia_repeticao_dentro_do_cooldown():
    controls = AlertControlManager(_FakeRedisClient())
    controls.allow_alert("a.com", "error", cooldown=300)

    assert controls.allow_alert("a.com", "error", cooldown=300) is False


def test_allow_alert_libera_apos_cooldown_expirar():
    """allow_alert() relies on the atomic SET's own `ex=cooldown` TTL to
    expire the cooldown key -- the fake client here doesn't model real
    time-based expiry, so the key's removal is simulated directly
    (exactly what a real Redis would have done once `cooldown` seconds
    passed). Once it's gone, a new alert is allowed again -- proving the
    NX check is keyed off the key's *presence*, not a separate manual
    timestamp comparison that could drift out of sync with the real TTL.
    """
    client = _FakeRedisClient()
    controls = AlertControlManager(client)
    controls.allow_alert("a.com", "error", cooldown=300)
    assert controls.allow_alert("a.com", "error", cooldown=300) is False  # still within cooldown

    del client._strings[controls._cooldown_key("a.com", "error")]  # simulate TTL expiry

    assert controls.allow_alert("a.com", "error", cooldown=300) is True


def test_allow_alert_e_isolado_por_tipo():
    controls = AlertControlManager(_FakeRedisClient())
    controls.allow_alert("a.com", "error", cooldown=300)

    assert controls.allow_alert("a.com", "latency", cooldown=300) is True


def test_allow_alert_e_isolado_por_dominio():
    controls = AlertControlManager(_FakeRedisClient())
    controls.allow_alert("a.com", "error", cooldown=300)

    assert controls.allow_alert("b.com", "error", cooldown=300) is True
