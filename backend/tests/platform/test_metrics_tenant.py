from app.platform.auth.platform_auth import PlatformAuth
from app.platform.metrics.platform_metrics import PlatformMetrics


def test_increment_com_organization_id_cria_bucket_por_org():
    metrics = PlatformMetrics()

    metrics.increment("logins", organization_id="org-a")

    assert metrics.get_metrics(organization_id="org-a")["counters"] == {"logins": 1}


def test_increment_sem_organization_id_usa_bucket_none():
    metrics = PlatformMetrics()

    metrics.increment("logins")

    # No org filter -> global aggregate, same as before this sprint.
    assert metrics.get_metrics()["counters"] == {"logins": 1}
    # Filtering by any specific org finds nothing, since it landed in the None bucket.
    assert metrics.get_metrics(organization_id="org-a")["counters"] == {}


def test_contadores_isolados_entre_organizacoes():
    metrics = PlatformMetrics()

    metrics.increment("logins", organization_id="org-a")
    metrics.increment("logins", organization_id="org-a")
    metrics.increment("logins", organization_id="org-b")

    assert metrics.get_metrics(organization_id="org-a")["counters"]["logins"] == 2
    assert metrics.get_metrics(organization_id="org-b")["counters"]["logins"] == 1


def test_get_metrics_sem_filtro_agrega_todas_as_orgs():
    metrics = PlatformMetrics()

    metrics.increment("logins", organization_id="org-a")
    metrics.increment("logins", organization_id="org-b")
    metrics.increment("logins")  # legacy/no-org event

    assert metrics.get_metrics()["counters"]["logins"] == 3


def test_timing_isolado_entre_organizacoes():
    metrics = PlatformMetrics()

    metrics.timing("login_time", 0.1, organization_id="org-a")
    metrics.timing("login_time", 0.3, organization_id="org-a")
    metrics.timing("login_time", 10.0, organization_id="org-b")

    org_a = metrics.get_metrics(organization_id="org-a")["timings"]["login_time"]
    assert org_a["count"] == 2
    assert org_a["avg"] == 0.2
    assert org_a["max"] == 0.3

    org_b = metrics.get_metrics(organization_id="org-b")["timings"]["login_time"]
    assert org_b["count"] == 1
    assert org_b["max"] == 10.0


def test_get_metrics_sem_filtro_agrega_timings_de_todas_as_orgs():
    metrics = PlatformMetrics()

    metrics.timing("login_time", 0.1, organization_id="org-a")
    metrics.timing("login_time", 0.2, organization_id="org-b")

    global_timing = metrics.get_metrics()["timings"]["login_time"]
    assert global_timing["count"] == 2


def test_organizacao_sem_metricas_retorna_vazio():
    metrics = PlatformMetrics()
    metrics.increment("logins", organization_id="org-a")

    assert metrics.get_metrics(organization_id="org-ghost") == {"counters": {}, "timings": {}}


def test_platform_auth_isola_metricas_entre_organizacoes():
    metrics = PlatformMetrics()
    auth = PlatformAuth(metrics=metrics)

    auth.register_user("a@test.com", "123456")
    auth.register_user("b@test.com", "123456")

    org_a = auth.get_user_organization("a@test.com")
    org_b = auth.get_user_organization("b@test.com")
    assert org_a != org_b

    assert metrics.get_metrics(organization_id=org_a)["counters"]["auth.register"] == 1
    assert metrics.get_metrics(organization_id=org_b)["counters"]["auth.register"] == 1
    assert metrics.get_metrics()["counters"]["auth.register"] == 2


def test_platform_auth_login_metrics_isoladas_por_org():
    metrics = PlatformMetrics()
    auth = PlatformAuth(metrics=metrics)
    auth.register_user("a@test.com", "123456")
    auth.register_user("b@test.com", "123456")
    org_a = auth.get_user_organization("a@test.com")
    org_b = auth.get_user_organization("b@test.com")

    auth.login("a@test.com", "123456")
    auth.login("a@test.com", "123456")
    auth.login("b@test.com", "123456")

    assert metrics.get_metrics(organization_id=org_a)["counters"]["auth.login.success"] == 2
    assert metrics.get_metrics(organization_id=org_b)["counters"]["auth.login.success"] == 1


def test_get_metrics_e_retrocompativel_sem_argumentos():
    """The exact contract Sprint 223's tests already rely on: get_metrics() with
    no arguments returns the same shape/totals as before this sprint existed.
    """
    metrics = PlatformMetrics()
    auth = PlatformAuth(metrics=metrics)

    auth.register_user("user@test.com", "123456")
    auth.login("user@test.com", "123456")

    data = metrics.get_metrics()
    assert data["counters"]["auth.register"] == 1
    assert data["counters"]["auth.login.success"] == 1
    assert data["timings"]["auth.login.duration"]["count"] == 1
