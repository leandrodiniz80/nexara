"""Tests for AlertDigestManager (Sprint 260)."""

from app.platform.metrics.alert_digest import AlertDigestManager


class _FakeRedisClient:
    def __init__(self):
        self._lists: dict[str, list[str]] = {}
        self._ttls: dict[str, int] = {}

    def rpush(self, key, value):
        self._lists.setdefault(key, []).append(value)

    def lrange(self, key, start, end):
        values = self._lists.get(key, [])
        return values[start:] if end == -1 else values[start : end + 1]

    def llen(self, key):
        return len(self._lists.get(key, []))

    def delete(self, key):
        self._lists.pop(key, None)
        self._ttls.pop(key, None)

    def expire(self, key, ttl):
        self._ttls[key] = ttl
        return True


def test_size_zero_por_padrao():
    digest = AlertDigestManager(_FakeRedisClient())

    assert digest.size("tenant-a") == 0


def test_add_incrementa_size():
    digest = AlertDigestManager(_FakeRedisClient())

    digest.add("tenant-a", {"domain": "a.com", "severity": "critical"})

    assert digest.size("tenant-a") == 1


def test_add_seta_expire_de_300_segundos():
    client = _FakeRedisClient()
    digest = AlertDigestManager(client)

    digest.add("tenant-a", {"domain": "a.com"})

    assert client._ttls[digest._key("tenant-a")] == 300


def test_flush_retorna_alertas_adicionados_na_ordem():
    digest = AlertDigestManager(_FakeRedisClient())
    digest.add("tenant-a", {"domain": "a.com", "severity": "critical"})
    digest.add("tenant-a", {"domain": "b.com", "severity": "high"})

    alerts = digest.flush("tenant-a")

    assert [a["domain"] for a in alerts] == ["a.com", "b.com"]


def test_flush_esvazia_o_digest():
    digest = AlertDigestManager(_FakeRedisClient())
    digest.add("tenant-a", {"domain": "a.com"})

    digest.flush("tenant-a")

    assert digest.size("tenant-a") == 0


def test_flush_vazio_retorna_lista_vazia():
    digest = AlertDigestManager(_FakeRedisClient())

    assert digest.flush("tenant-a") == []


def test_flush_e_isolado_por_tenant():
    digest = AlertDigestManager(_FakeRedisClient())
    digest.add("tenant-a", {"domain": "a.com"})
    digest.add("tenant-b", {"domain": "b.com"})

    flushed_a = digest.flush("tenant-a")

    assert len(flushed_a) == 1
    assert flushed_a[0]["domain"] == "a.com"
    assert digest.size("tenant-b") == 1


def test_flush_apos_ja_ter_sido_esvaziado_retorna_vazio():
    digest = AlertDigestManager(_FakeRedisClient())
    digest.add("tenant-a", {"domain": "a.com"})
    digest.flush("tenant-a")

    assert digest.flush("tenant-a") == []
