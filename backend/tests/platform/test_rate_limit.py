import time

import pytest

from app.platform.auth.platform_auth import PlatformAuth
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.cache.platform_cache import InMemoryCache
from app.platform.rate_limit.platform_rate_limiter import PlatformRateLimiter, RateLimitExceeded


def test_permite_ate_o_limite():
    limiter = PlatformRateLimiter()

    for _ in range(3):
        assert limiter.allow("k", limit=3, window_seconds=60) is True


def test_bloqueia_apos_o_limite():
    limiter = PlatformRateLimiter()

    for _ in range(3):
        limiter.allow("k", limit=3, window_seconds=60)

    assert limiter.allow("k", limit=3, window_seconds=60) is False


def test_chaves_diferentes_sao_independentes():
    limiter = PlatformRateLimiter()

    for _ in range(3):
        limiter.allow("a", limit=3, window_seconds=60)

    assert limiter.allow("a", limit=3, window_seconds=60) is False
    assert limiter.allow("b", limit=3, window_seconds=60) is True


def test_reseta_apos_a_janela():
    limiter = PlatformRateLimiter()
    limiter._requests["k"] = [time.time() - 120 for _ in range(5)]

    assert limiter.allow("k", limit=5, window_seconds=60) is True


def test_limite_none_e_ilimitado():
    limiter = PlatformRateLimiter()

    for _ in range(50):
        assert limiter.allow("k", limit=None, window_seconds=60) is True


def test_limite_negativo_e_ilimitado():
    limiter = PlatformRateLimiter()

    for _ in range(50):
        assert limiter.allow("k", limit=-1, window_seconds=60) is True


def test_platform_auth_sem_rate_limit_explicito_nao_afeta_uso_normal():
    auth = PlatformAuth()
    auth.register_user("user@test.com", "123456")

    assert auth.exists("user@test.com")
    assert auth.login("user@test.com", "123456") is not None


def test_check_rate_limit_permite_ate_o_limite_do_plano_free():
    auth = PlatformAuth()
    auth.register_user("user@test.com", "123456")

    for _ in range(100):
        auth.check_rate_limit("user@test.com")


def test_check_rate_limit_bloqueia_apos_o_limite_do_plano_free():
    auth = PlatformAuth()
    auth.register_user("user@test.com", "123456")

    for _ in range(100):
        auth.check_rate_limit("user@test.com")

    with pytest.raises(RateLimitExceeded):
        auth.check_rate_limit("user@test.com")


def test_planos_diferentes_tem_limites_diferentes():
    auth = PlatformAuth()
    auth.register_user("free@test.com", "123456")
    auth.register_user("pro@test.com", "123456")

    pro_org = auth.get_user_organization("pro@test.com")
    auth.set_organization_plan(pro_org, "pro")

    for _ in range(100):
        auth.check_rate_limit("free@test.com")
        auth.check_rate_limit("pro@test.com")

    with pytest.raises(RateLimitExceeded):
        auth.check_rate_limit("free@test.com")

    # pro's limit (1000/min) is far from exhausted at 100 requests
    auth.check_rate_limit("pro@test.com")


def test_plano_enterprise_e_ilimitado():
    auth = PlatformAuth()
    auth.register_user("user@test.com", "123456")
    org_id = auth.get_user_organization("user@test.com")
    auth.set_organization_plan(org_id, "enterprise")

    for _ in range(500):
        auth.check_rate_limit("user@test.com")


def test_reseta_apos_a_janela_no_check_rate_limit():
    auth = PlatformAuth()
    auth.register_user("user@test.com", "123456")

    for _ in range(100):
        auth.check_rate_limit("user@test.com")

    with pytest.raises(RateLimitExceeded):
        auth.check_rate_limit("user@test.com")

    old = time.time() - 120
    auth._rate_limiter._requests["user:user@test.com"] = [old] * 100
    org_id = auth.get_user_organization("user@test.com")
    auth._rate_limiter._requests[f"org:{org_id}"] = [old] * 100

    auth.check_rate_limit("user@test.com")


def test_rate_limit_e_isolado_por_usuario():
    auth = PlatformAuth()
    auth.register_user("a@test.com", "123456")
    auth.register_user("b@test.com", "123456")

    for _ in range(100):
        auth.check_rate_limit("a@test.com")

    with pytest.raises(RateLimitExceeded):
        auth.check_rate_limit("a@test.com")

    auth.check_rate_limit("b@test.com")


def test_rate_limit_funciona_com_cache_habilitado():
    auth = PlatformAuth(cache=InMemoryCache())
    auth.register_user("user@test.com", "123456")

    for _ in range(100):
        auth.check_rate_limit("user@test.com")

    with pytest.raises(RateLimitExceeded):
        auth.check_rate_limit("user@test.com")


def test_usuario_inexistente_nao_quebra_check_rate_limit():
    auth = PlatformAuth()

    auth.check_rate_limit("ghost@test.com")


def test_container_check_rate_limit_delega_para_auth():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("user@test.com", "123456")

    container.login("user@test.com", "123456")

    container.check_rate_limit()


def test_container_check_rate_limit_bloqueia_apos_limite():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("user@test.com", "123456")

    container.login("user@test.com", "123456")

    for _ in range(100):
        container.check_rate_limit()

    with pytest.raises(RateLimitExceeded):
        container.check_rate_limit()


def test_container_check_rate_limit_exige_autenticacao():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    with pytest.raises(PermissionError):
        container.check_rate_limit()


def test_container_execute_with_rate_limit():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("user@test.com", "123456")

    container.login("user@test.com", "123456")

    def acao():
        return "ok"

    assert container.execute_with_rate_limit(acao) == "ok"


def test_sistema_continua_funcionando_sem_usar_rate_limiter():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("admin@test.com", "123456", role="admin")

    container.login("admin@test.com", "123456")

    assert container.current_user_role() == "admin"
    container.require_role("admin")
