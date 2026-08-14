import pytest

from app.platform.auth.platform_auth import PlatformAuth
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.metrics.platform_metrics import PlatformMetrics
from app.platform.rate_limit.platform_rate_limiter import RateLimitExceeded


def test_increment_cria_contador_novo():
    metrics = PlatformMetrics()

    metrics.increment("logins")

    assert metrics.get_metrics()["counters"] == {"logins": 1}


def test_increment_acumula():
    metrics = PlatformMetrics()

    metrics.increment("logins")
    metrics.increment("logins")
    metrics.increment("logins", value=3)

    assert metrics.get_metrics()["counters"] == {"logins": 5}


def test_increment_valor_padrao_e_1():
    metrics = PlatformMetrics()

    metrics.increment("x")

    assert metrics.get_metrics()["counters"]["x"] == 1


def test_contadores_independentes_por_nome():
    metrics = PlatformMetrics()

    metrics.increment("a")
    metrics.increment("b", value=2)

    assert metrics.get_metrics()["counters"] == {"a": 1, "b": 2}


def test_timing_agrega_count_avg_max():
    metrics = PlatformMetrics()

    metrics.timing("login_time", 0.1)
    metrics.timing("login_time", 0.2)

    timings = metrics.get_metrics()["timings"]["login_time"]
    assert timings["count"] == 2
    assert timings["avg"] == pytest.approx(0.15)
    assert timings["max"] == pytest.approx(0.2)


def test_timing_unico_valor():
    metrics = PlatformMetrics()

    metrics.timing("x", 0.5)

    timings = metrics.get_metrics()["timings"]["x"]
    assert timings == {"count": 1, "avg": pytest.approx(0.5), "max": pytest.approx(0.5)}


def test_get_metrics_vazio_por_padrao():
    metrics = PlatformMetrics()

    assert metrics.get_metrics() == {"counters": {}, "timings": {}}


def test_get_metrics_counters_e_timings_independentes():
    metrics = PlatformMetrics()

    metrics.increment("a")
    metrics.timing("b", 0.3)

    data = metrics.get_metrics()
    assert data["counters"] == {"a": 1}
    assert data["timings"]["b"]["count"] == 1


def test_platform_auth_sem_metrics_nao_quebra():
    auth = PlatformAuth()

    auth.register_user("user@test.com", "123456")
    auth.login("user@test.com", "123456")

    assert auth.exists("user@test.com")


def test_register_user_incrementa_auth_register():
    metrics = PlatformMetrics()
    auth = PlatformAuth(metrics=metrics)

    auth.register_user("user@test.com", "123456")

    assert metrics.get_metrics()["counters"]["auth.register"] == 1


def test_create_organization_incrementa_org_created():
    metrics = PlatformMetrics()
    auth = PlatformAuth(metrics=metrics)

    auth.create_organization("Acme")

    assert metrics.get_metrics()["counters"]["org.created"] == 1


def test_register_user_cria_org_automaticamente_incrementa_ambos():
    metrics = PlatformMetrics()
    auth = PlatformAuth(metrics=metrics)

    auth.register_user("user@test.com", "123456")

    counters = metrics.get_metrics()["counters"]
    assert counters["auth.register"] == 1
    assert counters["org.created"] == 1


def test_login_bem_sucedido_incrementa_e_registra_timing():
    metrics = PlatformMetrics()
    auth = PlatformAuth(metrics=metrics)
    auth.register_user("user@test.com", "123456")

    auth.login("user@test.com", "123456")

    data = metrics.get_metrics()
    assert data["counters"]["auth.login.success"] == 1
    assert data["timings"]["auth.login.duration"]["count"] == 1
    assert data["timings"]["auth.login.duration"]["avg"] >= 0


def test_login_com_falha_nao_incrementa_success_mas_registra_timing():
    metrics = PlatformMetrics()
    auth = PlatformAuth(metrics=metrics)
    auth.register_user("user@test.com", "123456")

    auth.login("user@test.com", "wrong-password")

    data = metrics.get_metrics()
    assert "auth.login.success" not in data["counters"]
    assert data["timings"]["auth.login.duration"]["count"] == 1


def test_login_usuario_inexistente_registra_timing():
    metrics = PlatformMetrics()
    auth = PlatformAuth(metrics=metrics)

    auth.login("ghost@test.com", "whatever")

    data = metrics.get_metrics()
    assert data["timings"]["auth.login.duration"]["count"] == 1


def test_check_rate_limit_incrementa_rate_limit_hit_ao_bloquear():
    metrics = PlatformMetrics()
    auth = PlatformAuth(metrics=metrics)
    auth.register_user("user@test.com", "123456")

    for _ in range(100):
        auth.check_rate_limit("user@test.com")

    with pytest.raises(RateLimitExceeded):
        auth.check_rate_limit("user@test.com")

    assert metrics.get_metrics()["counters"]["rate_limit.hit"] == 1


def test_check_rate_limit_dentro_do_limite_nao_incrementa():
    metrics = PlatformMetrics()
    auth = PlatformAuth(metrics=metrics)
    auth.register_user("user@test.com", "123456")

    auth.check_rate_limit("user@test.com")

    assert "rate_limit.hit" not in metrics.get_metrics()["counters"]


def test_metricas_nao_contem_senha_ou_email_em_nomes():
    metrics = PlatformMetrics()
    auth = PlatformAuth(metrics=metrics)

    auth.register_user("user@test.com", "super-secret-password")
    auth.login("user@test.com", "super-secret-password")

    serialized = str(metrics.get_metrics())
    assert "super-secret-password" not in serialized
    assert "user@test.com" not in serialized


def test_container_repassa_metrics_para_auth():
    metrics = PlatformMetrics()
    container = PlatformContainer(bootstrap=PlatformBootstrap(), metrics=metrics)

    container.auth().register_user("user@test.com", "123456")

    assert metrics.get_metrics()["counters"]["auth.register"] == 1


def test_container_sem_metrics_funciona_normalmente():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    container.auth().register_user("user@test.com", "123456")
    session = container.login("user@test.com", "123456")

    assert session is not None
