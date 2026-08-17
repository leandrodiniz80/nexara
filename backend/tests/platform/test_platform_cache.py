from app.platform.auth.platform_auth import PlatformAuth
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.cache.platform_cache import InMemoryCache, PlatformCache


def test_platform_cache_base_get_retorna_none():
    cache = PlatformCache()

    assert cache.get("k") is None


def test_in_memory_cache_set_e_get():
    cache = InMemoryCache()

    cache.set("k", "v")

    assert cache.get("k") == "v"


def test_in_memory_cache_get_retorna_none_para_chave_inexistente():
    cache = InMemoryCache()

    assert cache.get("missing") is None


def test_in_memory_cache_respeita_ttl_ainda_valido():
    cache = InMemoryCache()

    cache.set("k", "v", ttl=100)

    assert cache.get("k") == "v"


def test_in_memory_cache_expira_apos_ttl():
    cache = InMemoryCache()

    cache.set("k", "v", ttl=-1)

    assert cache.get("k") is None


def test_in_memory_cache_sem_ttl_nunca_expira():
    cache = InMemoryCache()

    cache.set("k", "v")

    assert cache.get("k") == "v"


def test_in_memory_cache_delete():
    cache = InMemoryCache()
    cache.set("k", "v")

    cache.delete("k")

    assert cache.get("k") is None


def test_in_memory_cache_delete_chave_inexistente_nao_gera_erro():
    cache = InMemoryCache()

    cache.delete("missing")


def test_platform_auth_sem_cache_funciona_normalmente():
    auth = PlatformAuth()
    auth.register_user("user@test.com", "123456", role="admin", permissions=["read"])

    assert auth.get_user_role("user@test.com") == "admin"
    assert auth.get_user_permissions("user@test.com") == ["read"]


def test_get_user_role_usa_cache_quando_disponivel():
    cache = InMemoryCache()
    auth = PlatformAuth(cache=cache)
    auth.register_user("user@test.com", "123456", role="user")

    assert auth.get_user_role("user@test.com") == "user"

    auth.set_user_role_for_test("user@test.com", "admin")

    assert auth.get_user_role("user@test.com") == "user"


def test_get_user_permissions_usa_cache_quando_disponivel():
    cache = InMemoryCache()
    auth = PlatformAuth(cache=cache)
    auth.register_user("user@test.com", "123456", permissions=["read"])

    assert auth.get_user_permissions("user@test.com") == ["read"]

    auth.set_user_permissions_for_test("user@test.com", ["read", "write"])

    assert auth.get_user_permissions("user@test.com") == ["read"]


def test_get_user_organization_usa_cache_quando_disponivel():
    cache = InMemoryCache()
    auth = PlatformAuth(cache=cache)
    auth.register_user("user@test.com", "123456")
    original_org = auth.get_user_organization("user@test.com")

    other_org = auth.create_organization("Other Org")
    auth.set_user_organization_for_test("user@test.com", other_org)

    assert auth.get_user_organization("user@test.com") == original_org


def test_get_organization_plan_usa_cache_quando_disponivel():
    cache = InMemoryCache()
    auth = PlatformAuth(cache=cache)
    org_id = auth.create_organization("Acme")

    assert auth.get_organization_plan(org_id) == "free"

    auth.set_organization_plan_for_test(org_id, "pro")

    assert auth.get_organization_plan(org_id) == "free"


def test_register_user_invalida_cache_do_proprio_usuario():
    cache = InMemoryCache()
    auth = PlatformAuth(cache=cache)
    auth.register_user("user@test.com", "123456", role="user")
    auth.get_user_role("user@test.com")

    auth.register_user("user@test.com", "novasenha", role="admin")

    assert auth.get_user_role("user@test.com") == "admin"


def test_set_organization_plan_invalida_cache():
    cache = InMemoryCache()
    auth = PlatformAuth(cache=cache)
    org_id = auth.create_organization("Acme")
    auth.get_organization_plan(org_id)

    auth.set_organization_plan(org_id, "pro")

    assert auth.get_organization_plan(org_id) == "pro"


def test_add_user_to_organization_invalida_cache_do_usuario():
    cache = InMemoryCache()
    auth = PlatformAuth(cache=cache)
    auth.register_user("user@test.com", "123456")
    auth.get_user_organization("user@test.com")

    other_org = auth.create_organization("Other Org")
    auth.add_user_to_organization("user@test.com", other_org)

    assert cache.get("user_org:user@test.com") is None


def test_cache_nao_afeta_sessoes():
    cache = InMemoryCache()
    auth = PlatformAuth(cache=cache)
    auth.register_user("user@test.com", "123456")

    session = auth.login("user@test.com", "123456")

    assert cache.get(f"session:{session['token']}") is None
    assert auth.is_authenticated(session["token"])


def test_cache_nao_afeta_usage():
    cache = InMemoryCache()
    auth = PlatformAuth(cache=cache)
    org_id = auth.create_organization("Acme")

    auth.increment_usage(org_id, "requests_per_day")
    auth.increment_usage(org_id, "requests_per_day")

    assert auth.get_usage_for_org(org_id) == 2


def test_container_repassa_cache_para_auth():
    cache = InMemoryCache()
    container = PlatformContainer(bootstrap=PlatformBootstrap(), cache=cache)

    container.auth().register_user("user@test.com", "123456", role="admin")
    container.auth().get_user_role("user@test.com")

    assert cache.get("user_role:user@test.com") == "admin"


def test_container_sem_cache_funciona_normalmente():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("user@test.com", "123456", role="admin")

    container.login("user@test.com", "123456")

    assert container.current_user_role() == "admin"


def test_rbac_pbac_organizacao_e_billing_funcionam_igual_com_cache():
    cache = InMemoryCache()
    container = PlatformContainer(bootstrap=PlatformBootstrap(), cache=cache)
    container.auth().register_user(
        "owner@test.com", "123456", role="admin", permissions=["read"]
    )

    container.login("owner@test.com", "123456")

    assert container.current_user_role() == "admin"
    container.require_role("admin")

    assert container.current_user_permissions() == ["read"]
    container.require_permission("read")

    org_id = container.current_organization_id()
    container.require_same_organization(org_id)

    container.upgrade_plan("pro")

    assert container.auth().get_organization_plan(org_id) == "pro"
