from app.platform.metrics.incident_manager import IncidentManager


class _FakeRedisClient:
    """In-process double covering the subset of the API IncidentManager
    needs: get/set/lpush/ltrim/expire/delete/lrange."""

    def __init__(self):
        self._values: dict[str, str] = {}
        self._lists: dict[str, list[str]] = {}

    def get(self, key):
        return self._values.get(key)

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self._values:
            return None
        self._values[key] = value
        return True

    def delete(self, key):
        self._values.pop(key, None)

    def lpush(self, key, value):
        self._lists.setdefault(key, []).insert(0, value)

    def ltrim(self, key, start, end):
        values = self._lists.get(key, [])
        self._lists[key] = values[start:] if end == -1 else values[start : end + 1]

    def lrange(self, key, start, end):
        values = self._lists.get(key, [])
        return values[start:] if end == -1 else values[start : end + 1]

    def expire(self, key, ttl):
        return True


def test_open_or_update_novo_incidente_retorna_open():
    manager = IncidentManager(_FakeRedisClient())

    result = manager.open_or_update("a.com", "error", {"severity": "high"})

    assert result["status"] == "open"
    assert result["incident"]["domain"] == "a.com"
    assert result["incident"]["type"] == "error"
    assert result["incident"]["severity"] == "high"
    assert result["incident"]["count"] == 1


def test_open_or_update_repetido_retorna_ongoing_e_incrementa_count():
    client = _FakeRedisClient()
    manager = IncidentManager(client)

    manager.open_or_update("a.com", "error", {"severity": "medium"})
    result = manager.open_or_update("a.com", "error", {"severity": "high"})

    assert result["status"] == "ongoing"
    assert result["incident"]["count"] == 2
    # Severity is updated to the latest observation.
    assert result["incident"]["severity"] == "high"


def test_open_or_update_nao_duplica_incidente_ativo():
    """The explicit Sprint 253 requirement: never a second active incident
    for the same (domain, type) composite key — always update in place."""
    client = _FakeRedisClient()
    manager = IncidentManager(client)

    manager.open_or_update("a.com", "error", {"severity": "high"})
    manager.open_or_update("a.com", "error", {"severity": "high"})
    manager.open_or_update("a.com", "error", {"severity": "high"})

    assert len(manager.get_active("a.com")) == 1
    assert manager.get_active("a.com")[0]["count"] == 3


def test_open_or_update_tipos_diferentes_sao_incidentes_independentes():
    client = _FakeRedisClient()
    manager = IncidentManager(client)

    error_result = manager.open_or_update("a.com", "error", {"severity": "high"})
    latency_result = manager.open_or_update("a.com", "latency", {"severity": "high"})

    assert error_result["status"] == "open"
    assert latency_result["status"] == "open"
    assert len(manager.get_active("a.com")) == 2


def test_resolve_incidente_existente():
    client = _FakeRedisClient()
    manager = IncidentManager(client)
    manager.open_or_update("a.com", "error", {"severity": "high"})

    resolved = manager.resolve("a.com", "error")

    assert resolved is not None
    assert "duration" in resolved
    assert "resolved_at" in resolved


def test_resolve_incidente_inexistente_retorna_none():
    manager = IncidentManager(_FakeRedisClient())

    assert manager.resolve("never-had-one.com", "error") is None


def test_resolve_remove_o_incidente_ativo():
    client = _FakeRedisClient()
    manager = IncidentManager(client)
    manager.open_or_update("a.com", "error", {"severity": "high"})

    manager.resolve("a.com", "error")

    # A second resolve() call finds nothing — the active key is gone.
    assert manager.resolve("a.com", "error") is None
    assert manager.get_active("a.com") == []


def test_resolve_mescla_data_extra_no_registro_arquivado():
    client = _FakeRedisClient()
    manager = IncidentManager(client)
    manager.open_or_update("a.com", "error", {"severity": "high"})

    resolved = manager.resolve("a.com", "error", {"final_error_rate": 0.02})

    assert resolved["final_error_rate"] == 0.02


def test_resolve_sem_data_extra_funciona_normalmente():
    client = _FakeRedisClient()
    manager = IncidentManager(client)
    manager.open_or_update("a.com", "error", {"severity": "high"})

    resolved = manager.resolve("a.com", "error")

    assert resolved is not None


def test_resolve_adiciona_ao_historico_do_dominio():
    client = _FakeRedisClient()
    manager = IncidentManager(client)
    manager.open_or_update("a.com", "error", {"severity": "high"})

    manager.resolve("a.com", "error")

    history = manager.get_history("a.com")
    assert len(history) == 1
    assert history[0]["domain"] == "a.com"


def test_get_active_vazio_sem_incidentes():
    manager = IncidentManager(_FakeRedisClient())

    assert manager.get_active("a.com") == []


def test_get_active_retorna_apenas_tipos_realmente_abertos():
    client = _FakeRedisClient()
    manager = IncidentManager(client)
    manager.open_or_update("a.com", "error", {"severity": "high"})
    manager.open_or_update("a.com", "latency", {"severity": "medium"})

    manager.resolve("a.com", "latency")

    active = manager.get_active("a.com")
    assert len(active) == 1
    assert active[0]["type"] == "error"


def test_get_active_isolado_por_dominio():
    client = _FakeRedisClient()
    manager = IncidentManager(client)
    manager.open_or_update("a.com", "error", {"severity": "high"})
    manager.open_or_update("b.com", "error", {"severity": "high"})

    assert len(manager.get_active("a.com")) == 1
    assert len(manager.get_active("b.com")) == 1
    assert manager.get_active("never-seen.com") == []


def test_historico_isolado_por_dominio():
    """The real fix Sprint 252 needed: history keyed per-domain, not a
    single flat/global list shared by every tenant's domains."""
    client = _FakeRedisClient()
    manager = IncidentManager(client)
    manager.open_or_update("a.com", "error", {"severity": "high"})
    manager.open_or_update("b.com", "error", {"severity": "high"})

    manager.resolve("a.com", "error")
    manager.resolve("b.com", "error")

    assert len(manager.get_history("a.com")) == 1
    assert len(manager.get_history("b.com")) == 1
    assert manager.get_history("a.com")[0]["domain"] == "a.com"
    assert manager.get_history("never-seen.com") == []


def test_historico_mantem_ordem_mais_recente_primeiro():
    """Distinguishes entries by severity, not by `id` (which is
    second-granularity timestamped and could collide between two resolves
    happening within the same wall-clock second, as they will in a fast
    unit test) — `lpush` always prepends, so the most recently resolved
    incident is index 0 regardless of timing."""
    client = _FakeRedisClient()
    manager = IncidentManager(client)

    manager.open_or_update("a.com", "error", {"severity": "high"})
    manager.resolve("a.com", "error")

    manager.open_or_update("a.com", "error", {"severity": "critical"})
    manager.resolve("a.com", "error")

    history = manager.get_history("a.com")
    assert history[0]["severity"] == "critical"
    assert history[1]["severity"] == "high"


def test_historico_respeita_limit():
    client = _FakeRedisClient()
    manager = IncidentManager(client)

    for _ in range(5):
        manager.open_or_update("a.com", "error", {"severity": "high"})
        manager.resolve("a.com", "error")

    assert len(manager.get_history("a.com", limit=2)) == 2
