import pytest

from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.bootstrap.platform_kernel_facade import PlatformKernelFacade
from app.platform.tenant.tenant_context import TenantContext


def test_tenant_context_guarda_organization_id():
    context = TenantContext("org-1")

    assert context.organization_id == "org-1"


def test_get_tenant_id_exige_autenticacao():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    with pytest.raises(PermissionError):
        container.get_tenant_id()


def test_get_tenant_id_usa_organizacao_do_usuario_por_padrao():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("user@test.com", "123456")
    org_id = container.auth().get_user_organization("user@test.com")

    container.login("user@test.com", "123456")

    assert container.get_tenant_id() == org_id


def test_set_tenant_sobrepoe_a_organizacao_do_usuario():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("user@test.com", "123456")
    other_org = container.auth().create_organization("Other Org")

    container.login("user@test.com", "123456")
    container.set_tenant(other_org)

    assert container.get_tenant_id() == other_org


def test_ensure_same_tenant_permite_mesmo_tenant():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("user@test.com", "123456")
    org_id = container.auth().get_user_organization("user@test.com")

    container.login("user@test.com", "123456")

    container.ensure_same_tenant(org_id)


def test_ensure_same_tenant_bloqueia_tenant_diferente():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("user@test.com", "123456")
    other_org = container.auth().create_organization("Other Org")

    container.login("user@test.com", "123456")

    with pytest.raises(PermissionError):
        container.ensure_same_tenant(other_org)


def test_ensure_same_tenant_exige_autenticacao():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    with pytest.raises(PermissionError):
        container.ensure_same_tenant("some-org")


def test_isolamento_entre_duas_organizacoes():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("a@test.com", "123456")
    container.auth().register_user("b@test.com", "123456")

    org_a = container.auth().get_user_organization("a@test.com")
    org_b = container.auth().get_user_organization("b@test.com")
    assert org_a != org_b

    container.login("a@test.com", "123456")
    container.ensure_same_tenant(org_a)

    with pytest.raises(PermissionError):
        container.ensure_same_tenant(org_b)


def test_set_tenant_nao_afeta_outro_container():
    container_a = PlatformContainer(bootstrap=PlatformBootstrap())
    container_a.auth().register_user("user@test.com", "123456")
    org_id = container_a.auth().get_user_organization("user@test.com")
    container_a.login("user@test.com", "123456")
    container_a.set_tenant(org_id)

    container_b = PlatformContainer(bootstrap=PlatformBootstrap())
    container_b.auth().register_user("other@test.com", "123456")
    container_b.login("other@test.com", "123456")

    assert container_b.get_tenant_id() != org_id


def test_kernel_facade_delega_tenant():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    facade = PlatformKernelFacade(container=container)
    facade.container.auth().register_user("user@test.com", "123456")
    org_id = facade.container.auth().get_user_organization("user@test.com")

    facade.login("user@test.com", "123456")
    facade.set_tenant(org_id)

    assert facade.get_tenant_id() == org_id
    facade.ensure_same_tenant(org_id)
