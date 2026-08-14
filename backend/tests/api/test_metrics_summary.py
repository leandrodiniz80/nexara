"""Tests for GET /cdn/metrics/summary.

Two real issues in Sprint 243's own spec, both fixed here:

1. The store was a module-level singleton with no per-test override, and
   the spec's own test file never overrode it — every test in a session
   would share the same LoaderMetricsStore, making "sem dados" assertions
   order-dependent/flaky depending on what ran before them. Fixed with the
   same "construct fresh, override via dependency_overrides" pattern used
   for every other stateful dependency in this test suite.
2. `/metrics/summary` was left fully unauthenticated and let a caller filter
   by an arbitrary `domain` string — in a multi-tenant SaaS, aggregate
   traffic volume/error-rate/latency per domain is business-sensitive data;
   an anonymous caller (or an authenticated caller from a different
   organization) must not be able to read another tenant's numbers just by
   guessing its domain. Fixed by requiring auth and, when filtering by
   domain, requiring the caller's own organization to own that domain (same
   ownership check already established for domain registration, Sprint 236).
"""

from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.api.dependencies.metrics import get_metrics_store
from app.api.dependencies.tenant_resolver import DomainTenantResolver, get_domain_tenant_resolver
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.metrics.loader_metrics import LoaderMetricsStore


def _client() -> tuple[TestClient, PlatformContainer, LoaderMetricsStore, DomainTenantResolver]:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    store = LoaderMetricsStore()
    resolver = DomainTenantResolver()
    app.dependency_overrides[get_platform_container] = lambda: container
    app.dependency_overrides[get_metrics_store] = lambda: store
    app.dependency_overrides[get_domain_tenant_resolver] = lambda: resolver
    return TestClient(app), container, store, resolver


def _login(client: TestClient, email: str) -> str:
    client.post("/api/v1/auth/register", json={"email": email, "password": "123456"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def test_summary_endpoint_sem_autenticacao_bloqueia():
    client, _, _, _ = _client()

    res = client.get("/api/v1/cdn/metrics/summary")

    assert res.status_code == 401


def test_summary_sem_dados():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/summary", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    assert res.json()["total"] == 0
    assert res.json()["avg_duration"] is None


def test_summary_com_dados_filtrado_por_dominio_proprio():
    client, container, _, resolver = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("cliente.com", org_id)

    client.post(
        "/api/v1/cdn/metrics",
        json={"event": "success", "domain": "cliente.com", "duration": 100},
    )
    client.post("/api/v1/cdn/metrics", json={"event": "error", "domain": "cliente.com"})

    res = client.get(
        "/api/v1/cdn/metrics/summary?domain=cliente.com",
        headers={"Authorization": f"Bearer {token}"},
    )

    data = res.json()
    assert data["total"] == 2
    assert data["success"] == 1
    assert data["error"] == 1
    assert data["avg_duration"] == 100


def test_summary_filtrado_por_dominio_de_outra_organizacao_e_bloqueado():
    client, container, _, resolver = _client()
    token_a = _login(client, "owner-a@test.com")
    token_b = _login(client, "owner-b@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    resolver.register_domain("cliente-a.com", org_a)

    client.post(
        "/api/v1/cdn/metrics", json={"event": "success", "domain": "cliente-a.com"}
    )

    res = client.get(
        "/api/v1/cdn/metrics/summary?domain=cliente-a.com",
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert res.status_code == 403
    # Confirms org A can still read its own domain's data fine.
    own = client.get(
        "/api/v1/cdn/metrics/summary?domain=cliente-a.com",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert own.status_code == 200


def test_summary_filtrado_por_dominio_nao_registrado_e_bloqueado():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/summary?domain=never-registered.com",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 403


def test_summary_global_sem_filtro_agrega_todos_os_eventos():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    client.post("/api/v1/cdn/metrics", json={"event": "success", "domain": "a.com"})
    client.post("/api/v1/cdn/metrics", json={"event": "success", "domain": "b.com"})

    res = client.get(
        "/api/v1/cdn/metrics/summary", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.json()["total"] == 2


def test_store_isolado_entre_testes():
    """Confirms LoaderMetricsStore is properly overridable per test — a bare
    module-level singleton with no override point would leak events across
    the whole test session, same class of bug already caught for
    DomainTenantResolver."""
    client, _, store, _ = _client()

    assert store.summary()["total"] == 0
