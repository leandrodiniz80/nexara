"""Tests for AlertRateLimiter (Sprint 260).

Real issue in the spec, fixed here — see alert_rate_limiter.py's own
docstring: `EXPIRE` must only run on the *first* increment (`current ==
1`), not on every call — resetting the window's TTL on every alert would
mean a domain alerting continuously never actually gets rate-limited,
since the window would keep sliding forward forever. The spec's own code
already gated it correctly (`if current == 1`); these tests exist to
pin that behavior down explicitly.
"""

from app.platform.metrics.alert_rate_limiter import AlertRateLimiter


class _FakeRedisClient:
    def __init__(self):
        self._values: dict[str, int] = {}
        self.expire_calls: list[tuple[str, int]] = []

    def incr(self, key):
        self._values[key] = self._values.get(key, 0) + 1
        return self._values[key]

    def expire(self, key, ttl):
        self.expire_calls.append((key, ttl))
        return True


def test_allow_dentro_do_limite():
    limiter = AlertRateLimiter(_FakeRedisClient())

    for _ in range(5):
        assert limiter.allow("a.com", limit=5, window=300) is True


def test_allow_bloqueia_apos_exceder_o_limite():
    limiter = AlertRateLimiter(_FakeRedisClient())

    for _ in range(5):
        limiter.allow("a.com", limit=5, window=300)

    assert limiter.allow("a.com", limit=5, window=300) is False


def test_allow_e_isolado_por_dominio():
    limiter = AlertRateLimiter(_FakeRedisClient())
    for _ in range(5):
        limiter.allow("a.com", limit=5, window=300)

    assert limiter.allow("b.com", limit=5, window=300) is True


def test_expire_chamado_apenas_na_primeira_chamada():
    client = _FakeRedisClient()
    limiter = AlertRateLimiter(client)

    for _ in range(3):
        limiter.allow("a.com", limit=5, window=300)

    assert client.expire_calls == [("alert:rate:a.com", 300)]


def test_reset_apos_expirar_permite_novamente():
    """No real sleep needed: simulate the window's TTL having passed by
    resetting the fake counter directly, exactly what a real Redis EXPIRE
    would have done."""
    client = _FakeRedisClient()
    limiter = AlertRateLimiter(client)
    for _ in range(5):
        limiter.allow("a.com", limit=5, window=300)
    assert limiter.allow("a.com", limit=5, window=300) is False

    del client._values["alert:rate:a.com"]  # simulate window expiry

    assert limiter.allow("a.com", limit=5, window=300) is True


def test_limit_e_window_customizaveis():
    limiter = AlertRateLimiter(_FakeRedisClient())

    assert limiter.allow("a.com", limit=1, window=60) is True
    assert limiter.allow("a.com", limit=1, window=60) is False
