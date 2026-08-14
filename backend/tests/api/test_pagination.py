"""Tests for pagination + filtering added to /cdn/metrics/incidents,
/cdn/metrics/incidents/active, and /cdn/metrics/audit (Sprint 264).

Real issues in the spec, fixed here — see cdn.py/loader_metrics.py for
the implementation-level explanation:

1. `store._paginate(...)` — a private, underscore-prefixed method called
   directly from the router; every other router-facing capability on
   `LoaderMetricsStore` is public. Renamed to `paginate()`
   (`@staticmethod`, since it never touches `self`/`self._storage`).
2. `per_page: int = Query(20, le=100)` — missing `ge=1`, exactly the
   mistake the spec's own "BUGS A EVITAR" list warns against (item 5:
   "Não esquecer ge=1, le=100"). Fixed with both bounds.
3. `container.audit.get_events()` (no `event=` filter) inside the new
   `/metrics/audit` pagination code — would have silently widened that
   endpoint from "cross-tenant admin reads only" to "every audit event
   ever logged". Fixed: the `event=metrics_global_access` filter is kept.
4. Wholesale envelope replacement (dropping `total`/`scope` in favor of
   only `meta`) on `/metrics/incidents(/active)` — would have broken
   every existing consumer/test of those endpoints, violating this
   sprint's own "don't break existing endpoints" rule. `meta` is
   additive here; `items`/`total`/`scope` are unchanged.

`per_page` is a positional page-request (int) throughout, not a
`GLOBAL "type"` query param that shadows the Python builtin — this file
tests `incident_type` (the query param name), filtering the incident
record's own `"type"` field.
"""

from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.api.dependencies.metrics import get_metrics_store
from app.api.dependencies.tenant_resolver import DomainTenantResolver, get_domain_tenant_resolver
from app.platform.audit.platform_audit import PlatformAudit
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.metrics.incident_manager import IncidentManager
from app.platform.metrics.loader_metrics import LoaderMetricsStore
from app.platform.metrics.metrics_storage import AggregatedRedisMetricsStorage


class _FakeRedisClient:
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


def _client(
    storage=None,
) -> tuple[TestClient, PlatformContainer, LoaderMetricsStore, DomainTenantResolver]:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap(), audit=PlatformAudit())
    store = LoaderMetricsStore(storage=storage)
    resolver = DomainTenantResolver()
    app.dependency_overrides[get_platform_container] = lambda: container
    app.dependency_overrides[get_metrics_store] = lambda: store
    app.dependency_overrides[get_domain_tenant_resolver] = lambda: resolver
    return TestClient(app), container, store, resolver


def _login(client: TestClient, email: str) -> str:
    client.post("/api/v1/auth/register", json={"email": email, "password": "123456"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def _register_admin(client: TestClient, email: str) -> str:
    client.post(
        "/api/v1/auth/register", json={"email": email, "password": "123456", "role": "admin"}
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


# --- LoaderMetricsStore.paginate() (unit) -------------------------------


def test_paginate_pagina_cheia_tem_has_next_verdadeiro():
    items = list(range(25))

    result = LoaderMetricsStore.paginate(items, page=1, per_page=20)

    assert result["items"] == list(range(20))
    assert result["meta"] == {"total": 25, "page": 1, "per_page": 20, "has_next": True}


def test_paginate_ultima_pagina_tem_has_next_falso():
    items = list(range(25))

    result = LoaderMetricsStore.paginate(items, page=2, per_page=20)

    assert result["items"] == list(range(20, 25))
    assert result["meta"]["has_next"] is False


def test_paginate_pagina_alem_do_fim_retorna_vazio_sem_erro():
    items = list(range(5))

    result = LoaderMetricsStore.paginate(items, page=99, per_page=20)

    assert result["items"] == []
    assert result["meta"]["total"] == 5
    assert result["meta"]["has_next"] is False


def test_paginate_lista_vazia():
    result = LoaderMetricsStore.paginate([], page=1, per_page=20)

    assert result == {
        "items": [],
        "meta": {"total": 0, "page": 1, "per_page": 20, "has_next": False},
    }


def test_paginate_callable_como_staticmethod_sem_instancia():
    """Called directly on the class, no LoaderMetricsStore() instance
    needed -- the reason /metrics/audit can use it without a `store`
    dependency."""
    result = LoaderMetricsStore.paginate([1, 2, 3], page=1, per_page=2)

    assert result["items"] == [1, 2]


# --- GET /metrics/incidents: pagination + filters -----------------------


def _storage_with_incidents():
    fake_client = _FakeRedisClient()
    manager = IncidentManager(fake_client)
    storage = AggregatedRedisMetricsStorage(fake_client, incident_manager=manager)
    return storage, manager


def test_incidents_per_page_acima_de_100_e_bloqueado():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/incidents?per_page=101",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 422


def test_incidents_page_zero_e_bloqueado():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/incidents?page=0", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 422


def test_incidents_resposta_inclui_items_total_scope_e_meta():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/incidents", headers={"Authorization": f"Bearer {token}"}
    )

    data = res.json()
    assert "items" in data
    assert "total" in data
    assert "scope" in data
    assert "meta" in data
    assert set(data["meta"].keys()) == {"total", "page", "per_page", "has_next"}


def test_incidents_pagina_corretamente_por_per_page():
    storage, manager = _storage_with_incidents()
    client, container, store, resolver = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    org_id = container.auth().get_user_organization("admin@test.com")
    for i in range(5):
        domain = f"d{i}.com"
        resolver.register_domain(domain, org_id)
        manager.open_or_update(domain, "error", {"severity": "high"})
        manager.resolve(domain, "error")

    first_page = client.get(
        "/api/v1/cdn/metrics/incidents?page=1&per_page=2",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    second_page = client.get(
        "/api/v1/cdn/metrics/incidents?page=2&per_page=2",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()

    assert len(first_page["items"]) == 2
    assert first_page["meta"] == {"total": 5, "page": 1, "per_page": 2, "has_next": True}
    assert len(second_page["items"]) == 2
    assert second_page["meta"]["has_next"] is True
    # No overlap between pages.
    first_domains = {item["domain"] for item in first_page["items"]}
    second_domains = {item["domain"] for item in second_page["items"]}
    assert first_domains.isdisjoint(second_domains)


def test_incidents_filtro_por_severity():
    storage, manager = _storage_with_incidents()
    client, container, store, resolver = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    org_id = container.auth().get_user_organization("admin@test.com")
    resolver.register_domain("critical.com", org_id)
    resolver.register_domain("medium.com", org_id)
    manager.open_or_update("critical.com", "error", {"severity": "critical"})
    manager.resolve("critical.com", "error")
    manager.open_or_update("medium.com", "error", {"severity": "medium"})
    manager.resolve("medium.com", "error")

    res = client.get(
        "/api/v1/cdn/metrics/incidents?severity=critical",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    data = res.json()
    assert data["meta"]["total"] == 1
    assert data["items"][0]["domain"] == "critical.com"


def test_incidents_filtros_combinados_severity_e_domain():
    storage, manager = _storage_with_incidents()
    client, container, store, resolver = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    org_id = container.auth().get_user_organization("admin@test.com")
    resolver.register_domain("a.com", org_id)
    resolver.register_domain("b.com", org_id)
    manager.open_or_update("a.com", "error", {"severity": "critical"})
    manager.resolve("a.com", "error")
    manager.open_or_update("b.com", "error", {"severity": "critical"})
    manager.resolve("b.com", "error")

    res = client.get(
        "/api/v1/cdn/metrics/incidents?severity=critical&domain=a.com",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    data = res.json()
    assert data["meta"]["total"] == 1
    assert data["items"][0]["domain"] == "a.com"


def test_incidents_filtro_por_incident_type():
    storage, manager = _storage_with_incidents()
    client, container, store, resolver = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    org_id = container.auth().get_user_organization("admin@test.com")
    resolver.register_domain("a.com", org_id)
    manager.open_or_update("a.com", "error", {"severity": "high"})
    manager.resolve("a.com", "error")
    manager.open_or_update("a.com", "latency", {"severity": "high"})
    manager.resolve("a.com", "latency")

    res = client.get(
        "/api/v1/cdn/metrics/incidents?incident_type=latency",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    data = res.json()
    assert data["meta"]["total"] == 1
    assert data["items"][0]["type"] == "latency"


# --- GET /metrics/incidents/active: pagination + filters ------------------


def test_incidents_active_per_page_acima_de_100_e_bloqueado():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/incidents/active?per_page=200",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 422


def test_incidents_active_filtro_por_severity():
    storage, manager = _storage_with_incidents()
    client, container, store, resolver = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    org_id = container.auth().get_user_organization("admin@test.com")
    resolver.register_domain("critical.com", org_id)
    resolver.register_domain("high.com", org_id)
    manager.open_or_update("critical.com", "error", {"severity": "critical"})
    manager.open_or_update("high.com", "error", {"severity": "high"})

    res = client.get(
        "/api/v1/cdn/metrics/incidents/active?severity=high",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    data = res.json()
    assert data["meta"]["total"] == 1
    assert data["items"][0]["domain"] == "high.com"


# --- GET /metrics/audit: pagination ---------------------------------------


def test_audit_per_page_acima_de_100_e_bloqueado():
    client, _, _, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/audit?per_page=500",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert res.status_code == 422


def test_audit_resposta_inclui_meta():
    client, _, _, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/audit", headers={"Authorization": f"Bearer {admin_token}"}
    )

    data = res.json()
    assert "meta" in data
    assert set(data["meta"].keys()) == {"total", "page", "per_page", "has_next"}


def test_audit_ainda_filtra_apenas_eventos_de_acesso_global():
    """The filter regression this sprint could have introduced: paginating
    /metrics/audit must not widen it to show every audit event type."""
    client, container, _, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/audit", headers={"Authorization": f"Bearer {admin_token}"}
    )

    # Registering the admin itself logs no metrics_global_access event
    # (only actually reading cross-tenant /metrics/* data does) -- if the
    # event filter were dropped, registration-adjacent events could leak
    # through instead.
    assert res.json()["items"] == []


def test_audit_pagina_corretamente_apos_multiplos_acessos_globais():
    client, container, _, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")

    for _ in range(3):
        client.get(
            "/api/v1/cdn/metrics/dashboard", headers={"Authorization": f"Bearer {admin_token}"}
        )

    first_page = client.get(
        "/api/v1/cdn/metrics/audit?page=1&per_page=2",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    second_page = client.get(
        "/api/v1/cdn/metrics/audit?page=2&per_page=2",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()

    assert len(first_page["items"]) == 2
    assert first_page["meta"] == {"total": 3, "page": 1, "per_page": 2, "has_next": True}
    assert len(second_page["items"]) == 1
    assert second_page["meta"]["has_next"] is False
