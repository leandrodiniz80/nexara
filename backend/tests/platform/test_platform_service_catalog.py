import inspect

import pytest
from pydantic import ValidationError

from app.platform.bootstrap import platform_service_catalog, platform_service_catalog_factory
from app.platform.bootstrap.platform_service_catalog import PlatformServiceCatalog
from app.platform.bootstrap.platform_service_catalog_factory import (
    build_platform_service_catalog,
)
from app.platform.bootstrap.platform_service_descriptor import PlatformServiceDescriptor


def _descriptor(name: str) -> PlatformServiceDescriptor:
    return PlatformServiceDescriptor(name=name, instance=object())


def test_catalogo_vazio():
    catalog = PlatformServiceCatalog()

    assert catalog.services() == []


def test_services_retorna_os_descritores():
    descriptor_a = _descriptor("a")
    descriptor_b = _descriptor("b")
    catalog = PlatformServiceCatalog(descriptors=(descriptor_a, descriptor_b))

    assert catalog.services() == [descriptor_a, descriptor_b]


def test_find_existente():
    descriptor = _descriptor("a")
    catalog = PlatformServiceCatalog(descriptors=(descriptor,))

    assert catalog.find("a") is descriptor


def test_find_inexistente_retorna_none():
    catalog = PlatformServiceCatalog(descriptors=(_descriptor("a"),))

    assert catalog.find("does_not_exist") is None


def test_exists():
    catalog = PlatformServiceCatalog(descriptors=(_descriptor("a"),))

    assert catalog.exists("a") is True
    assert catalog.exists("does_not_exist") is False


def test_ordem_preservada():
    descriptor_a = _descriptor("a")
    descriptor_b = _descriptor("b")
    descriptor_c = _descriptor("c")
    catalog = PlatformServiceCatalog(descriptors=(descriptor_a, descriptor_b, descriptor_c))

    assert [d.name for d in catalog.services()] == ["a", "b", "c"]


def test_identidade_preservada():
    descriptor = _descriptor("a")
    catalog = PlatformServiceCatalog(descriptors=(descriptor,))

    assert catalog.services()[0] is descriptor
    assert catalog.find("a") is descriptor


def test_lista_retornada_e_nova_a_cada_chamada():
    catalog = PlatformServiceCatalog(descriptors=(_descriptor("a"),))

    assert catalog.services() is not catalog.services()
    assert catalog.services() == catalog.services()


def test_imutabilidade_rejects_attribute_assignment():
    catalog = PlatformServiceCatalog(descriptors=(_descriptor("a"),))

    with pytest.raises(ValidationError):
        catalog.descriptors = ()


def test_injecao_uses_exactly_the_descriptors_provided():
    descriptor = _descriptor("a")

    catalog = PlatformServiceCatalog(descriptors=(descriptor,))

    assert catalog.descriptors == (descriptor,)


def test_conhece_exclusivamente_platform_service_descriptor():
    source = inspect.getsource(platform_service_catalog)

    assert "PlatformServiceDescriptor" in source
    assert "PlatformBootstrap" not in source
    assert "PlatformContainer" not in source
    assert "PlatformKernelFacade" not in source
    assert "PlatformServiceRegistry" not in source
    assert "PlatformServiceResolver" not in source


def test_ausencia_de_runtime():
    source = inspect.getsource(platform_service_catalog)
    assert "app.runtime" not in source
    assert "Runtime" not in source


def test_ausencia_de_operations():
    source = inspect.getsource(platform_service_catalog)
    assert "app.operations" not in source
    assert "Operations" not in source


def test_ausencia_de_lifecycle():
    source = inspect.getsource(platform_service_catalog)
    assert "app.platform.lifecycle" not in source
    assert "Lifecycle" not in source


def test_ausencia_de_health():
    source = inspect.getsource(platform_service_catalog)
    assert "app.platform.health" not in source
    assert "Health" not in source


def test_ausencia_de_events():
    source = inspect.getsource(platform_service_catalog)
    assert "app.platform.events" not in source
    assert "Events" not in source


def test_ausencia_de_capabilities():
    source = inspect.getsource(platform_service_catalog)
    assert "app.platform.capabilities" not in source
    assert "Capabilities" not in source


def test_ausencia_de_features():
    source = inspect.getsource(platform_service_catalog)
    assert "app.platform.features" not in source
    assert "Features" not in source


def test_ausencia_de_command_bus():
    source = inspect.getsource(platform_service_catalog)
    assert "app.application.command_bus" not in source
    assert "CommandBus" not in source


def test_ausencia_de_query_bus():
    source = inspect.getsource(platform_service_catalog)
    assert "app.application.query_bus" not in source
    assert "QueryBus" not in source


def test_factory_retorna_platform_service_catalog():
    catalog = build_platform_service_catalog(services=())

    assert isinstance(catalog, PlatformServiceCatalog)


def test_factory_preserva_os_descritores_fornecidos():
    descriptor = _descriptor("a")

    catalog = build_platform_service_catalog(services=(descriptor,))

    assert catalog.services() == [descriptor]
    assert catalog.find("a") is descriptor


def test_factory_conhece_exclusivamente_platform_service_descriptor():
    source = inspect.getsource(platform_service_catalog_factory)

    assert "PlatformServiceDescriptor" in source
    assert "PlatformBootstrap" not in source
    assert "PlatformContainer" not in source
    assert "PlatformKernelFacade" not in source
    assert "PlatformServiceRegistry" not in source
    assert "PlatformServiceResolver" not in source


def test_factory_nenhuma_referencia_a_dominios():
    source = inspect.getsource(platform_service_catalog_factory)

    assert "app.runtime" not in source
    assert "app.operations" not in source
    assert "app.platform.lifecycle" not in source
    assert "app.platform.health" not in source
    assert "app.platform.events" not in source
    assert "app.platform.capabilities" not in source
    assert "app.platform.features" not in source
    assert "app.application.command_bus" not in source
    assert "app.application.query_bus" not in source
