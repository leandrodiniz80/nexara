import inspect

import pytest
from pydantic import ValidationError

from app.platform.bootstrap import platform_kernel_facade, platform_kernel_facade_factory
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.bootstrap.platform_kernel_facade import PlatformKernelFacade
from app.platform.bootstrap.platform_kernel_facade_factory import (
    build_default_platform_kernel_facade,
)

_SERVICE_NAMES = [
    "runtime",
    "operations",
    "command_bus",
    "query_bus",
    "application",
    "presentation",
    "platform_interface",
    "orchestrator",
    "health",
    "lifecycle",
    "events",
    "capabilities",
    "features",
]


@pytest.mark.parametrize("service_name", _SERVICE_NAMES)
def test_facade_resolve_preserva_identidade(service_name: str):
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)
    direct_instance = getattr(bootstrap, service_name)()

    assert facade.resolve(service_name) is direct_instance


def test_kernel_resolve_health_retorna_exatamente_bootstrap_health():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    resolved = facade.resolve("health")

    assert resolved is bootstrap.health()


def test_kernel_exists_health():
    bootstrap = PlatformBootstrap()
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=bootstrap))

    assert facade.exists("health") is True


def test_kernel_list_inclui_health():
    bootstrap = PlatformBootstrap()
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=bootstrap))

    names = {descriptor.name for descriptor in facade.list()}

    assert "health" in names


def test_kernel_health_retorna_exatamente_container_health():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    assert facade.health() is container.health()


def test_kernel_health_chama_container_health_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = PlatformContainer.health

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(PlatformContainer, "health", _spy)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.health()

    assert calls["count"] == 1


def test_kernel_health_nao_reconstroi(monkeypatch):
    from app.platform.bootstrap import platform_bootstrap

    calls = {"count": 0}
    original = platform_bootstrap.build_default_platform_health_facade

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(platform_bootstrap, "build_default_platform_health_facade", _spy)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.health()
    facade.health()

    assert calls["count"] == 1


def test_kernel_lifecycle_retorna_exatamente_container_lifecycle():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    assert facade.lifecycle() is container.lifecycle()


def test_kernel_lifecycle_identidade_preservada():
    bootstrap = PlatformBootstrap()
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=bootstrap))

    assert facade.lifecycle() is bootstrap.lifecycle()


def test_kernel_lifecycle_chama_container_lifecycle_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = PlatformContainer.lifecycle

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(PlatformContainer, "lifecycle", _spy)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.lifecycle()

    assert calls["count"] == 1


def test_kernel_lifecycle_nao_reconstroi(monkeypatch):
    from app.platform.bootstrap import platform_bootstrap

    calls = {"count": 0}
    original = platform_bootstrap.build_default_platform_lifecycle

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(platform_bootstrap, "build_default_platform_lifecycle", _spy)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.lifecycle()
    facade.lifecycle()

    assert calls["count"] == 1


def test_kernel_capabilities_retorna_exatamente_container_capabilities():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    assert facade.capabilities() is container.capabilities()


def test_kernel_capabilities_identidade_preservada():
    bootstrap = PlatformBootstrap()
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=bootstrap))

    assert facade.capabilities() is bootstrap.capabilities()


def test_kernel_capabilities_chama_container_capabilities_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = PlatformContainer.capabilities

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(PlatformContainer, "capabilities", _spy)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.capabilities()

    assert calls["count"] == 1


def test_kernel_capabilities_nao_reconstroi(monkeypatch):
    from app.platform.bootstrap import platform_bootstrap

    calls = {"count": 0}
    original = platform_bootstrap.build_default_platform_capabilities

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(platform_bootstrap, "build_default_platform_capabilities", _spy)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.capabilities()
    facade.capabilities()

    assert calls["count"] == 1


def test_kernel_features_retorna_exatamente_container_features():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    assert facade.features() is container.features()


def test_kernel_features_identidade_preservada():
    bootstrap = PlatformBootstrap()
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=bootstrap))

    assert facade.features() is bootstrap.features()


def test_kernel_features_chama_container_features_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = PlatformContainer.features

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(PlatformContainer, "features", _spy)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.features()

    assert calls["count"] == 1


def test_kernel_features_nao_reconstroi(monkeypatch):
    from app.platform.bootstrap import platform_bootstrap

    calls = {"count": 0}
    original = platform_bootstrap.build_default_platform_features

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(platform_bootstrap, "build_default_platform_features", _spy)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.features()
    facade.features()

    assert calls["count"] == 1


def test_kernel_events_retorna_exatamente_container_resolve_events():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    assert facade.events() is container.resolve("events")


def test_kernel_events_identidade_preservada():
    bootstrap = PlatformBootstrap()
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=bootstrap))

    assert facade.events() is bootstrap.events()


def test_kernel_events_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = PlatformContainer.resolve

    def _spy(self, name):
        calls["count"] += 1
        return original(self, name)

    monkeypatch.setattr(PlatformContainer, "resolve", _spy)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.events()

    assert calls["count"] == 1


def test_kernel_events_nao_reconstroi(monkeypatch):
    from app.platform.bootstrap import platform_bootstrap

    calls = {"count": 0}
    original = platform_bootstrap.build_default_platform_events

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(platform_bootstrap, "build_default_platform_events", _spy)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.events()
    facade.events()

    assert calls["count"] == 1


def test_kernel_catalog_retorna_exatamente_container_catalog():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    assert facade.catalog() is container.catalog()


def test_kernel_catalog_identidade_preservada():
    bootstrap = PlatformBootstrap()
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=bootstrap))

    assert facade.catalog() is bootstrap.catalog()


def test_kernel_catalog_chama_container_catalog_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = PlatformContainer.catalog

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(PlatformContainer, "catalog", _spy)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.catalog()

    assert calls["count"] == 1


def test_kernel_catalog_delega_para_container(monkeypatch):
    calls = {"count": 0}
    original = PlatformContainer.catalog

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(PlatformContainer, "catalog", _spy)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.catalog()

    assert calls["count"] == 1


def test_kernel_catalog_nao_usa_list():
    source = inspect.getsource(PlatformKernelFacade.catalog)

    assert "list(" not in source


def test_kernel_catalog_nao_usa_projections():
    source = inspect.getsource(PlatformKernelFacade.catalog)

    assert "projections(" not in source


def test_kernel_catalog_sem_logica():
    source = inspect.getsource(PlatformKernelFacade.catalog)

    assert "for " not in source
    assert "{" not in source
    assert "[" not in source


def test_kernel_catalog_nao_reconstroi(monkeypatch):
    from app.platform.bootstrap import platform_bootstrap

    calls = {"count": 0}
    original = platform_bootstrap.build_platform_service_catalog

    def _spy(*args, **kwargs):
        calls["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(platform_bootstrap, "build_platform_service_catalog", _spy)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.catalog()
    facade.catalog()

    assert calls["count"] == 1


def test_kernel_catalog_sem_logica_adicional(monkeypatch):
    sentinel = object()

    def _fake_catalog(self):
        return sentinel

    monkeypatch.setattr(PlatformContainer, "catalog", _fake_catalog)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))

    assert facade.catalog() is sentinel


def test_kernel_projections_retorna_container_projections():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    assert facade.projections() == container.projections()


def test_kernel_projections_identidade_preservada():
    bootstrap = PlatformBootstrap()
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=bootstrap))

    assert facade.projections()["catalog"] is bootstrap.catalog()


def test_kernel_projections_chama_container_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = PlatformContainer.projections

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(PlatformContainer, "projections", _spy)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.projections()

    assert calls["count"] == 1


def test_kernel_projections_contem_services():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    projections = facade.projections()

    assert "services" in projections
    assert projections["services"] == container.list()


def test_kernel_projections_services_identidade_preservada():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    projected_services = facade.projections()["services"]

    for projected, listed in zip(projected_services, container.list()):
        assert projected is listed


def test_kernel_projections_contem_service_names():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    projections = facade.projections()

    assert "service_names" in projections
    assert projections["service_names"] == tuple(d.name for d in container.list())


def test_kernel_projections_service_names_identidade_preservada():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    assert facade.projections()["service_names"] == facade.projections()["service_names"]


def test_kernel_projections_contem_service_map():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    service_map = facade.projections()["service_map"]

    for descriptor in container.list():
        assert service_map[descriptor.name] is descriptor.instance


def test_kernel_projections_service_map_identidade_preservada():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    service_map = facade.projections()["service_map"]

    for descriptor in container.list():
        assert service_map[descriptor.name] is descriptor.instance


def test_kernel_service_names_retorna_container_service_names():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    assert facade.service_names() == container.service_names()


def test_kernel_service_names_identidade_preservada():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    assert facade.service_names() == facade.service_names()


def test_kernel_service_names_chama_container_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = PlatformContainer.service_names

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(PlatformContainer, "service_names", _spy)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.service_names()

    assert calls["count"] == 1


def test_kernel_service_names_delega_para_container(monkeypatch):
    calls = {"count": 0}
    original = PlatformContainer.service_names

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(PlatformContainer, "service_names", _spy)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.service_names()

    assert calls["count"] == 1


def test_kernel_service_names_elementos_preservam_identidade():
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))

    first = facade.service_names()
    second = facade.service_names()

    for a, b in zip(first, second):
        assert a is b


def test_kernel_service_names_nao_usa_list():
    source = inspect.getsource(PlatformKernelFacade.service_names)

    assert "list(" not in source


def test_kernel_service_names_nao_usa_projections():
    source = inspect.getsource(PlatformKernelFacade.service_names)

    assert "projections(" not in source


def test_kernel_service_names_sem_logica():
    source = inspect.getsource(PlatformKernelFacade.service_names)

    assert "for " not in source
    assert "{" not in source
    assert "[" not in source


def test_kernel_service_map_retorna_container_service_map():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    assert facade.service_map() == container.service_map()


def test_kernel_service_map_identidade_preservada():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    service_map = facade.service_map()

    for descriptor in container.list():
        assert service_map[descriptor.name] is descriptor.instance


def test_kernel_service_map_chama_container_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = PlatformContainer.service_map

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(PlatformContainer, "service_map", _spy)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.service_map()

    assert calls["count"] == 1


def test_kernel_service_map_delega_para_container(monkeypatch):
    calls = {"count": 0}
    original = PlatformContainer.service_map

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(PlatformContainer, "service_map", _spy)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.service_map()

    assert calls["count"] == 1


def test_kernel_service_map_nao_usa_list():
    source = inspect.getsource(PlatformKernelFacade.service_map)

    assert "list(" not in source


def test_kernel_service_map_nao_usa_projections():
    source = inspect.getsource(PlatformKernelFacade.service_map)

    assert "projections(" not in source


def test_kernel_service_map_sem_logica():
    source = inspect.getsource(PlatformKernelFacade.service_map)

    assert "for " not in source
    assert "{" not in source
    assert "[" not in source


def test_kernel_services_projection_retorna_container_services_projection():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    assert facade.services_projection() == container.services_projection()


def test_kernel_services_projection_identidade_preservada():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    for projected, listed in zip(facade.services_projection(), container.list()):
        assert projected is listed


def test_kernel_services_projection_chama_container_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = PlatformContainer.services_projection

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(PlatformContainer, "services_projection", _spy)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.services_projection()

    assert calls["count"] == 1


def test_kernel_services_projection_retorna_container():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    facade = PlatformKernelFacade(container=container)

    assert facade.services_projection() == container.services_projection()


def test_kernel_services_projection_sem_logica():
    source = inspect.getsource(PlatformKernelFacade.services_projection)

    assert "resolve(" not in source
    assert "registry" not in source
    assert "build" not in source


def test_kernel_read_models_retorna_container_read_models():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    assert facade.read_models() == container.read_models()


def test_kernel_read_models_identidade_preservada():
    bootstrap = PlatformBootstrap()
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=bootstrap))

    assert facade.read_models()["catalog"] is bootstrap.catalog()


def test_kernel_read_models_chama_container_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = PlatformContainer.read_models

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(PlatformContainer, "read_models", _spy)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.read_models()

    assert calls["count"] == 1


def test_kernel_read_models_v1_retorna_container_read_models_v1():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    assert facade.read_models_v1() == container.read_models_v1()


def test_kernel_read_models_v1_identidade_preservada():
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))

    first = facade.read_models_v1()
    second = facade.read_models_v1()

    assert first == second
    assert first["catalog"] is second["catalog"]


def test_kernel_read_models_v1_chama_container_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = PlatformContainer.read_models_v1

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(PlatformContainer, "read_models_v1", _spy)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.read_models_v1()

    assert calls["count"] == 1


def test_kernel_read_models_v1_sem_logica_adicional():
    source = inspect.getsource(PlatformKernelFacade.read_models_v1)

    assert "resolve(" not in source
    assert "registry" not in source
    assert "build" not in source


def test_kernel_read_models_v1_nao_reconstroi(monkeypatch):
    from app.platform.bootstrap import platform_read_models_compat

    calls = {"count": 0}
    original = platform_read_models_compat.get_read_models_v1

    def _spy(data):
        calls["count"] += 1
        return original(data)

    monkeypatch.setattr(platform_read_models_compat, "get_read_models_v1", _spy)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.read_models_v1()
    facade.read_models_v1()

    assert calls["count"] == 2


def test_kernel_read_models_v1_version_delega_para_container(monkeypatch):
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    called = {"count": 0}

    def fake(self):
        called["count"] += 1
        return "1.0.0"

    monkeypatch.setattr(PlatformContainer, "read_models_v1_version", fake)

    result = facade.read_models_v1_version()

    assert result == "1.0.0"
    assert called["count"] == 1


def test_kernel_read_models_v1_version_sem_logica():
    source = inspect.getsource(PlatformKernelFacade.read_models_v1_version)

    assert "self.container.read_models_v1_version()" in source
    assert "for " not in source
    assert "if " not in source


def test_kernel_read_models_v2_delega_para_container(monkeypatch):
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    facade = PlatformKernelFacade(container=container)

    called = {"count": 0}

    def fake(self):
        called["count"] += 1
        return "ok"

    monkeypatch.setattr(PlatformContainer, "read_models_v2", fake)

    assert facade.read_models_v2() == "ok"
    assert called["count"] == 1


def test_kernel_read_models_v2_sem_logica():
    source = inspect.getsource(PlatformKernelFacade.read_models_v2)

    assert "for " not in source
    assert "if " not in source


def test_kernel_read_models_v2_igual_container():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    assert facade.read_models_v2() == container.read_models_v2()


def test_kernel_read_models_v2_preserva_registro():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    data = facade.read_models_v2()

    assert container._is_v2(data) is True


def test_kernel_read_models_version_retorna_container():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    assert facade.read_models_version() == container.read_models_version()


def test_kernel_read_models_version_delega_para_container(monkeypatch):
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    called = {"count": 0}

    def fake(self):
        called["count"] += 1
        return "1.0.0"

    monkeypatch.setattr(PlatformContainer, "read_models_version", fake)

    result = facade.read_models_version()

    assert result == "1.0.0"
    assert called["count"] == 1


def test_kernel_read_models_version_sem_logica():
    source = inspect.getsource(PlatformKernelFacade.read_models_version)

    assert "self.container.read_models_version()" in source
    assert "for " not in source
    assert "if " not in source
    assert "list(" not in source
    assert "dict(" not in source
    assert "tuple(" not in source


def test_kernel_read_models_version_nao_usa_projections_ou_resolve():
    source = inspect.getsource(PlatformKernelFacade.read_models_version)

    assert "projections(" not in source
    assert "resolve(" not in source
    assert "registry" not in source.lower()


def test_kernel_read_models_tipo_typed_dict():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    result = facade.read_models()

    assert isinstance(result, dict)
    assert "services" in result
    assert "service_names" in result
    assert "service_map" in result
    assert "catalog" in result


def test_kernel_read_models_igual_container():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    assert facade.read_models() == container.read_models()


def test_kernel_read_models_identidade_catalog_preservada():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    result = facade.read_models()

    assert result["catalog"] is container.catalog()


def test_kernel_read_models_sem_logica():
    source = inspect.getsource(PlatformKernelFacade.read_models)

    assert "self.container.read_models()" in source
    assert "for " not in source
    assert "if " not in source
    assert "list(" not in source
    assert "dict(" not in source


def test_kernel_read_models_nao_usa_projections_ou_resolve():
    source = inspect.getsource(PlatformKernelFacade.read_models)

    assert "projections(" not in source
    assert "resolve(" not in source
    assert "registry" not in source.lower()


def test_kernel_catalog_projection_retorna_container():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    facade = PlatformKernelFacade(container=container)

    assert facade.catalog_projection() is container.catalog_projection()


def test_kernel_catalog_projection_identidade_preservada():
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))

    first = facade.catalog_projection()
    second = facade.catalog_projection()

    assert first is second


def test_kernel_catalog_projection_chama_container_uma_vez(monkeypatch):
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    facade = PlatformKernelFacade(container=container)

    calls = {"count": 0}

    def fake(self):
        calls["count"] += 1
        return object()

    monkeypatch.setattr(PlatformContainer, "catalog_projection", fake)

    facade.catalog_projection()

    assert calls["count"] == 1


def test_kernel_catalog_projection_sem_logica():
    source = inspect.getsource(PlatformKernelFacade.catalog_projection)

    assert "resolve(" not in source
    assert "registry" not in source
    assert "build" not in source


def test_kernel_service_names_projection_retorna_container():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    facade = PlatformKernelFacade(container=container)

    assert facade.service_names_projection() == container.service_names_projection()


def test_kernel_service_names_projection_identidade_preservada():
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))

    first = facade.service_names_projection()
    second = facade.service_names_projection()

    assert first == second


def test_kernel_service_names_projection_chama_container_uma_vez(monkeypatch):
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    facade = PlatformKernelFacade(container=container)

    calls = {"count": 0}

    def fake(self):
        calls["count"] += 1
        return ()

    monkeypatch.setattr(PlatformContainer, "service_names_projection", fake)

    facade.service_names_projection()

    assert calls["count"] == 1


def test_kernel_service_names_projection_sem_logica():
    source = inspect.getsource(PlatformKernelFacade.service_names_projection)

    assert "resolve(" not in source
    assert "registry" not in source
    assert "build" not in source


def test_kernel_facade_metodos_publicos_sao_delegacao_pura():
    services_source = inspect.getsource(PlatformKernelFacade.services)
    assert "self.container." in services_source
    assert "list(" not in services_source
    assert "projections(" not in services_source
    assert "resolve(" not in services_source
    assert "registry" not in services_source
    assert "for " not in services_source
    assert "{" not in services_source
    assert "[" not in services_source

    service_map_source = inspect.getsource(PlatformKernelFacade.service_map)
    assert "self.container." in service_map_source
    assert "list(" not in service_map_source
    assert "projections(" not in service_map_source
    assert "resolve(" not in service_map_source
    assert "registry" not in service_map_source
    assert "for " not in service_map_source
    assert "{" not in service_map_source

    service_names_source = inspect.getsource(PlatformKernelFacade.service_names)
    assert "self.container." in service_names_source
    assert "list(" not in service_names_source
    assert "projections(" not in service_names_source
    assert "resolve(" not in service_names_source
    assert "registry" not in service_names_source
    assert "for " not in service_names_source
    assert "{" not in service_names_source

    catalog_source = inspect.getsource(PlatformKernelFacade.catalog)
    assert "self.container." in catalog_source
    assert "list(" not in catalog_source
    assert "projections(" not in catalog_source
    assert "resolve(" not in catalog_source
    assert "registry" not in catalog_source
    assert "for " not in catalog_source
    assert "{" not in catalog_source
    assert "[" not in catalog_source

    projections_source = inspect.getsource(PlatformKernelFacade.projections)
    assert "self.container." in projections_source
    assert "list(" not in projections_source
    assert "resolve(" not in projections_source
    assert "registry" not in projections_source
    assert "for " not in projections_source
    assert "{" not in projections_source

    read_models_source = inspect.getsource(PlatformKernelFacade.read_models)
    assert "self.container." in read_models_source
    assert "list(" not in read_models_source
    assert "projections(" not in read_models_source
    assert "resolve(" not in read_models_source
    assert "registry" not in read_models_source
    assert "for " not in read_models_source
    assert "{" not in read_models_source
    assert "[" not in read_models_source

    read_models_v1_source = inspect.getsource(PlatformKernelFacade.read_models_v1)
    assert "self.container." in read_models_v1_source
    assert "list(" not in read_models_v1_source
    assert "projections(" not in read_models_v1_source
    assert "resolve(" not in read_models_v1_source
    assert "registry" not in read_models_v1_source
    assert "for " not in read_models_v1_source
    assert "{" not in read_models_v1_source
    assert "[" not in read_models_v1_source


def test_kernel_facade_metodos_publicos_expostos():
    methods = {
        name
        for name in dir(PlatformKernelFacade)
        if not name.startswith("_") and callable(getattr(PlatformKernelFacade, name))
    }

    expected = {
        "services",
        "service_map",
        "service_names",
        "catalog",
        "projections",
        "read_models",
        "read_models_v1",
    }

    assert methods >= expected


def test_kernel_facade_nao_expoe_metodos_do_container():
    assert not hasattr(PlatformKernelFacade, "service_map_projection")
    assert not hasattr(PlatformKernelFacade, "_build_projections")
    assert not hasattr(PlatformKernelFacade, "registry")


def test_kernel_facade_todos_metodos_sao_delegacao_pura():
    services_source = inspect.getsource(PlatformKernelFacade.services)
    services_body = services_source.split("\n", 1)[1]
    assert "self.container." in services_source
    assert "for " not in services_source
    assert "if " not in services_source
    assert "{" not in services_source
    assert "[" not in services_body
    assert "resolve(" not in services_source
    assert "registry" not in services_source
    assert "list(" not in services_source

    service_map_source = inspect.getsource(PlatformKernelFacade.service_map)
    service_map_body = service_map_source.split("\n", 1)[1]
    assert "self.container." in service_map_source
    assert "for " not in service_map_source
    assert "if " not in service_map_source
    assert "{" not in service_map_source
    assert "[" not in service_map_body
    assert "resolve(" not in service_map_source
    assert "registry" not in service_map_source
    assert "list(" not in service_map_source

    service_names_source = inspect.getsource(PlatformKernelFacade.service_names)
    service_names_body = service_names_source.split("\n", 1)[1]
    assert "self.container." in service_names_source
    assert "for " not in service_names_source
    assert "if " not in service_names_source
    assert "{" not in service_names_source
    assert "[" not in service_names_body
    assert "resolve(" not in service_names_source
    assert "registry" not in service_names_source
    assert "list(" not in service_names_source

    catalog_source = inspect.getsource(PlatformKernelFacade.catalog)
    catalog_body = catalog_source.split("\n", 1)[1]
    assert "self.container." in catalog_source
    assert "for " not in catalog_source
    assert "if " not in catalog_source
    assert "{" not in catalog_source
    assert "[" not in catalog_body
    assert "resolve(" not in catalog_source
    assert "registry" not in catalog_source
    assert "list(" not in catalog_source

    projections_source = inspect.getsource(PlatformKernelFacade.projections)
    projections_body = projections_source.split("\n", 1)[1]
    assert "self.container." in projections_source
    assert "for " not in projections_source
    assert "if " not in projections_source
    assert "{" not in projections_source
    assert "[" not in projections_body
    assert "resolve(" not in projections_source
    assert "registry" not in projections_source
    assert "list(" not in projections_source

    read_models_source = inspect.getsource(PlatformKernelFacade.read_models)
    read_models_body = read_models_source.split("\n", 1)[1]
    assert "self.container." in read_models_source
    assert "for " not in read_models_source
    assert "if " not in read_models_source
    assert "{" not in read_models_source
    assert "[" not in read_models_body
    assert "resolve(" not in read_models_source
    assert "registry" not in read_models_source
    assert "list(" not in read_models_source

    read_models_v1_source = inspect.getsource(PlatformKernelFacade.read_models_v1)
    read_models_v1_body = read_models_v1_source.split("\n", 1)[1]
    assert "self.container." in read_models_v1_source
    assert "for " not in read_models_v1_source
    assert "if " not in read_models_v1_source
    assert "{" not in read_models_v1_source
    assert "[" not in read_models_v1_body
    assert "resolve(" not in read_models_v1_source
    assert "registry" not in read_models_v1_source
    assert "list(" not in read_models_v1_source


def test_kernel_facade_superficie_publica_fechada():
    methods = {
        name
        for name in dir(PlatformKernelFacade)
        if not name.startswith("_") and callable(getattr(PlatformKernelFacade, name))
    }

    expected = {
        "services",
        "service_map",
        "service_names",
        "catalog",
        "projections",
        "read_models",
        "read_models_v1",
    }

    assert methods >= expected


def test_kernel_facade_nao_expoe_internals_container():
    assert not hasattr(PlatformKernelFacade, "service_map_projection")
    assert not hasattr(PlatformKernelFacade, "_build_projections")
    assert not hasattr(PlatformKernelFacade, "registry")


def test_kernel_facade_nao_constroi_estrutura():
    for method_name in (
        "services",
        "service_map",
        "service_names",
        "catalog",
        "projections",
        "read_models",
        "read_models_v1",
    ):
        source = inspect.getsource(getattr(PlatformKernelFacade, method_name))

        assert "dict(" not in source
        assert "tuple(" not in source
        assert "list(" not in source
        assert "set(" not in source
        assert "for " not in source


def test_kernel_facade_sem_encadeamento():
    method_names = (
        "services",
        "service_map",
        "service_names",
        "catalog",
        "projections",
        "read_models",
        "read_models_v1",
    )

    for method_name in method_names:
        source = inspect.getsource(getattr(PlatformKernelFacade, method_name))

        assert source.count("self.container.") == 1

        for other_name in method_names:
            assert f"self.{other_name}(" not in source


def test_resolve_continua_funcionando_apos_events():
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))

    for service_name in _SERVICE_NAMES:
        assert facade.resolve(service_name) is not None


def test_exists_continua_funcionando_apos_events():
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))

    assert facade.exists("events") is True


def test_list_continua_funcionando_apos_events():
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))

    names = {descriptor.name for descriptor in facade.list()}
    assert names == set(_SERVICE_NAMES)


def test_services_continua_funcionando_apos_events():
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))

    names = {descriptor.name for descriptor in facade.services()}
    assert names == set(_SERVICE_NAMES)


def test_health_continua_funcionando_apos_events():
    bootstrap = PlatformBootstrap()
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=bootstrap))

    assert facade.health() is bootstrap.health()


def test_lifecycle_continua_funcionando_apos_events():
    bootstrap = PlatformBootstrap()
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=bootstrap))

    assert facade.lifecycle() is bootstrap.lifecycle()


def test_kernel_services_retorna_exatamente_container_list(monkeypatch):
    sentinel = [object(), object()]

    def _fake_list(self):
        return sentinel

    monkeypatch.setattr(PlatformContainer, "list", _fake_list)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))

    assert facade.services() is sentinel


def test_kernel_services_identidade_preservada(monkeypatch):
    sentinel = [object()]

    def _fake_list(self):
        return sentinel

    monkeypatch.setattr(PlatformContainer, "list", _fake_list)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))

    assert facade.services() is sentinel
    assert facade.services() is sentinel


def test_kernel_services_chama_container_list_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = PlatformContainer.list

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(PlatformContainer, "list", _spy)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.services()

    assert calls["count"] == 1


def test_kernel_services_delega_para_projection(monkeypatch):
    calls = {"count": 0}
    original = PlatformContainer.services_projection

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(PlatformContainer, "services_projection", _spy)

    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.services()

    assert calls["count"] == 1


def test_kernel_services_nao_usa_list():
    source = inspect.getsource(PlatformKernelFacade.services)

    assert "list(" not in source


def test_kernel_services_nao_usa_projections():
    source = inspect.getsource(PlatformKernelFacade.services)

    assert "projections(" not in source


def test_kernel_services_sem_logica():
    source = inspect.getsource(PlatformKernelFacade.services)

    assert "for " not in source
    assert "{" not in source
    assert "[" not in source


def test_kernel_services_sem_reconstrucao_retorna_dados_consistentes():
    bootstrap = PlatformBootstrap()
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=bootstrap))

    names = {descriptor.name for descriptor in facade.services()}

    assert names == set(_SERVICE_NAMES)


def test_kernel_services_conteudo_igual_a_container_list():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    services_names = {d.name for d in facade.services()}
    list_names = {d.name for d in container.list()}

    assert services_names == list_names


def test_services_contem_exatamente_treze_servicos():
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))

    assert len(facade.services()) == 13


def test_services_ordem_preservada():
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))

    names = [descriptor.name for descriptor in facade.services()]

    assert names == _SERVICE_NAMES


def test_services_sem_duplicacao():
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))

    names = [descriptor.name for descriptor in facade.services()]

    assert len(names) == len(set(names))


def test_services_preserva_identidade_dos_descritores():
    bootstrap = PlatformBootstrap()
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=bootstrap))

    for descriptor in facade.services():
        direct_instance = getattr(bootstrap, descriptor.name)()
        assert descriptor.instance is direct_instance


def test_services_e_consistente_com_container_list():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    facade = PlatformKernelFacade(container=container)

    facade_descriptors = facade.services()
    container_descriptors = container.list()

    assert len(facade_descriptors) == len(container_descriptors)
    for facade_descriptor, container_descriptor in zip(
        facade_descriptors, container_descriptors
    ):
        assert facade_descriptor.name == container_descriptor.name
        assert facade_descriptor.instance is container_descriptor.instance


def test_services_confirma_presenca_de_todos_os_servicos_oficiais():
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))

    names = {descriptor.name for descriptor in facade.services()}

    for service_name in [
        "runtime",
        "operations",
        "command_bus",
        "query_bus",
        "application",
        "presentation",
        "platform_interface",
        "orchestrator",
        "health",
        "lifecycle",
        "events",
        "capabilities",
        "features",
    ]:
        assert service_name in names


def test_resolve_continua_funcionando_apos_services():
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))

    for service_name in _SERVICE_NAMES:
        assert facade.resolve(service_name) is not None


def test_exists_continua_funcionando_apos_services():
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))

    assert facade.exists("runtime") is True


def test_list_continua_funcionando_apos_services():
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))

    names = {descriptor.name for descriptor in facade.list()}
    assert names == set(_SERVICE_NAMES)


def test_health_continua_funcionando_apos_services():
    bootstrap = PlatformBootstrap()
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=bootstrap))

    assert facade.health() is bootstrap.health()


def test_lifecycle_continua_funcionando_apos_services():
    bootstrap = PlatformBootstrap()
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=bootstrap))

    assert facade.lifecycle() is bootstrap.lifecycle()


def test_resolve_inexistente_levanta_key_error():
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))

    with pytest.raises(KeyError):
        facade.resolve("does_not_exist")


def test_exists():
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))

    for service_name in _SERVICE_NAMES:
        assert facade.exists(service_name) is True
    assert facade.exists("does_not_exist") is False


def test_list():
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))

    names = {descriptor.name for descriptor in facade.list()}

    assert names == set(_SERVICE_NAMES)


def test_imutabilidade_rejects_attribute_assignment():
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))

    with pytest.raises(ValidationError):
        facade.container = PlatformContainer(bootstrap=PlatformBootstrap())


def test_injecao_uses_exactly_the_container_provided():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    facade = PlatformKernelFacade(container=container)

    assert facade.container is container


def test_utiliza_exclusivamente_platform_container():
    source = inspect.getsource(platform_kernel_facade)

    assert "container.resolve(name)" in source
    assert "container.exists(name)" in source
    assert "container.list()" in source
    assert "container.health()" in source
    assert "container.lifecycle()" in source
    assert 'container.resolve("events")' in source
    assert "container.capabilities()" in source
    assert "container.features()" in source
    assert "container.catalog()" in source


def test_nenhuma_referencia_a_componentes_concretos_de_catalog():
    source = inspect.getsource(platform_kernel_facade)

    assert "PlatformServiceCatalog" not in source
    assert "PlatformServiceRegistry" not in source
    assert "PlatformServiceResolver" not in source
    assert "PlatformBootstrap" not in source


def test_container_chamado_exatamente_uma_vez(monkeypatch):
    from app.platform.bootstrap import platform_container_factory

    calls = {"count": 0}
    original = platform_container_factory.build_default_platform_container

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(
        platform_kernel_facade_factory, "build_default_platform_container", _spy
    )

    build_default_platform_kernel_facade()

    assert calls["count"] == 1


def test_platform_kernel_facade_conhece_apenas_platform_container():
    source = inspect.getsource(platform_kernel_facade)

    assert "PlatformContainer" in source
    assert "PlatformBootstrap" not in source
    assert "PlatformServiceResolver" not in source
    assert "PlatformServiceRegistry" not in source
    assert "PlatformServiceDescriptor" not in source


def test_nenhuma_referencia_a_componentes_concretos_de_health():
    source = inspect.getsource(platform_kernel_facade)

    assert "PlatformHealthFacade" not in source
    assert "HealthCoordinator" not in source
    assert "HealthMonitor" not in source
    assert "HealthReportService" not in source
    assert "HealthExecutor" not in source
    assert "HealthManager" not in source
    assert "HealthCheckRegistry" not in source
    assert "HealthCheck" not in source


def test_nenhuma_referencia_a_componentes_concretos_de_lifecycle():
    source = inspect.getsource(platform_kernel_facade)

    assert "PlatformLifecycle" not in source
    assert "LifecycleExecutor" not in source
    assert "LifecycleManager" not in source
    assert "LifecycleStarter" not in source
    assert "LifecycleStopper" not in source
    assert "LifecycleParticipant" not in source
    assert "LifecycleParticipantRegistry" not in source


def test_nenhuma_referencia_a_componentes_concretos_de_capabilities():
    source = inspect.getsource(platform_kernel_facade)

    assert "PlatformCapabilities" not in source
    assert "CapabilityExecutor" not in source
    assert "CapabilityManager" not in source
    assert "CapabilityRegistry" not in source
    assert "Capability" not in source


def test_nenhuma_referencia_a_componentes_concretos_de_features():
    source = inspect.getsource(platform_kernel_facade)

    assert "PlatformFeatures" not in source
    assert "FeatureExecutor" not in source
    assert "FeatureManager" not in source
    assert "FeatureRegistry" not in source
    assert "Feature" not in source


def test_nenhuma_referencia_a_componentes_concretos_de_events():
    source = inspect.getsource(platform_kernel_facade)

    assert "PlatformEvents" not in source
    assert "PlatformEventExecutor" not in source
    assert "PlatformEventManager" not in source
    assert "EventRegistry" not in source
    assert "PlatformEvent" not in source


def test_facade_nenhuma_factory():
    source = inspect.getsource(platform_kernel_facade)

    assert "factory" not in source.lower()
    assert "build_default" not in source


def test_facade_nenhum_engine():
    source = inspect.getsource(platform_kernel_facade)

    assert "app.runtime" not in source
    assert "app.operations" not in source


def test_facade_nenhum_service_concreto():
    source = inspect.getsource(platform_kernel_facade)

    assert "CommandBusService" not in source
    assert "QueryBusService" not in source
    assert "PublicUseCaseService" not in source
    assert "PresentationFacade" not in source
    assert "PlatformInterface" not in source
    assert "PlatformExecutionOrchestrator" not in source


def test_facade_nenhuma_instanciacao_direta():
    source = inspect.getsource(platform_kernel_facade)

    forbidden_instantiations = [
        "RuntimeEngine(",
        "OperationsCoordinator(",
        "CommandBus(",
        "QueryBus(",
        "ExecutionPipeline(",
        "PlatformExecutionOrchestrator(",
        "PresentationFacade(",
        "PlatformInterface(",
        "ApplicationInterfaceService(",
    ]
    for pattern in forbidden_instantiations:
        assert pattern not in source


def test_factory_retorna_platform_kernel_facade():
    facade = build_default_platform_kernel_facade()

    assert isinstance(facade, PlatformKernelFacade)


def test_kernel_facade_factory_nenhuma_referencia_alem_de_container():
    source = inspect.getsource(platform_kernel_facade_factory)

    assert "PlatformBootstrap" not in source
    assert "PlatformServiceResolver" not in source
    assert "PlatformServiceRegistry" not in source


def test_kernel_login_delega():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("user@example.com", "correct-horse-battery-staple")
    facade = PlatformKernelFacade(container=container)

    session = facade.login("user@example.com", "correct-horse-battery-staple")

    assert session is not None
    assert session["email"] == "user@example.com"


def test_kernel_current_user():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("user@example.com", "correct-horse-battery-staple")
    facade = PlatformKernelFacade(container=container)

    facade.login("user@example.com", "correct-horse-battery-staple")

    user = facade.current_user()

    assert user["email"] == "user@example.com"


def test_kernel_logout():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("user@example.com", "correct-horse-battery-staple")
    facade = PlatformKernelFacade(container=container)

    facade.login("user@example.com", "correct-horse-battery-staple")
    facade.logout()

    assert facade.current_user() is None


def test_kernel_auth_retorna_container_auth():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    facade = PlatformKernelFacade(container=container)

    assert facade.auth() is container.auth()


def test_kernel_require_auth():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("user@example.com", "correct-horse-battery-staple")
    facade = PlatformKernelFacade(container=container)

    facade.login("user@example.com", "correct-horse-battery-staple")

    user = facade.require_auth()

    assert user["email"] == "user@example.com"


def test_kernel_require_auth_bloqueia():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    facade = PlatformKernelFacade(container=container)

    with pytest.raises(PermissionError):
        facade.require_auth()


def test_kernel_current_user_email():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    facade = PlatformKernelFacade(container=container)

    facade.auth().register_user("user@test.com", "123")
    facade.login("user@test.com", "123")

    assert facade.current_user_email() == "user@test.com"


def test_kernel_execute_authenticated():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    facade = PlatformKernelFacade(container=container)

    facade.auth().register_user("user@test.com", "123")
    facade.login("user@test.com", "123")

    def acao():
        return "ok"

    assert facade.execute_authenticated(acao) == "ok"


def test_kernel_execute_authenticated_bloqueia():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    facade = PlatformKernelFacade(container=container)

    def acao():
        return "ok"

    with pytest.raises(PermissionError):
        facade.execute_authenticated(acao)


def test_kernel_require_role():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    facade = PlatformKernelFacade(container=container)

    facade.auth().register_user("admin@test.com", "123", role="admin")
    facade.login("admin@test.com", "123")

    facade.require_role("admin")


def test_kernel_require_role_bloqueia():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    facade = PlatformKernelFacade(container=container)

    facade.auth().register_user("user@test.com", "123", role="user")
    facade.login("user@test.com", "123")

    with pytest.raises(PermissionError):
        facade.require_role("admin")


def test_kernel_current_user_role():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    facade = PlatformKernelFacade(container=container)

    facade.auth().register_user("admin@test.com", "123", role="admin")
    facade.login("admin@test.com", "123")

    assert facade.current_user_role() == "admin"


def test_kernel_execute_with_role():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    facade = PlatformKernelFacade(container=container)

    facade.auth().register_user("admin@test.com", "123", role="admin")
    facade.login("admin@test.com", "123")

    def acao():
        return "ok"

    assert facade.execute_with_role("admin", acao) == "ok"


def test_kernel_execute_secure():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    facade = PlatformKernelFacade(container=container)

    facade.auth().register_user("user@test.com", "123")
    facade.login("user@test.com", "123")

    def fn():
        return "ok"

    assert facade.execute_secure(fn) == "ok"


def test_kernel_execute_secure_com_role():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    facade = PlatformKernelFacade(container=container)

    facade.auth().register_user("admin@test.com", "123", role="admin")
    facade.login("admin@test.com", "123")

    def fn():
        return "admin_ok"

    assert facade.execute_secure(fn, role="admin") == "admin_ok"


def test_kernel_execute_secure_bloqueia():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    facade = PlatformKernelFacade(container=container)

    def fn():
        return "fail"

    with pytest.raises(PermissionError):
        facade.execute_secure(fn)


def test_kernel_permission():
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    auth = facade.auth()

    auth.register_user("user@test.com", "123", permissions=["x"])
    facade.login("user@test.com", "123")

    facade.require_permission("x")


def test_kernel_permission_bloqueia():
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    auth = facade.auth()

    auth.register_user("user@test.com", "123", permissions=[])
    facade.login("user@test.com", "123")

    with pytest.raises(PermissionError):
        facade.require_permission("x")


def test_kernel_current_user_permissions():
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.auth().register_user("user@test.com", "123", permissions=["x", "y"])
    facade.login("user@test.com", "123")

    assert facade.current_user_permissions() == ["x", "y"]


def test_kernel_execute_with_permission():
    facade = PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))
    facade.auth().register_user("user@test.com", "123", permissions=["x"])
    facade.login("user@test.com", "123")

    def fn():
        return "ok"

    assert facade.execute_with_permission("x", fn) == "ok"


def test_kernel_current_organization_id():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    facade = PlatformKernelFacade(container=container)

    org_id = container.auth().create_organization("Acme")
    container.auth().register_user("user@test.com", "123", organization_id=org_id)
    facade.login("user@test.com", "123")

    assert facade.current_organization_id() == org_id


def test_kernel_require_same_organization_bloqueia():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    facade = PlatformKernelFacade(container=container)

    org_id = container.auth().create_organization("Acme")
    container.auth().register_user("user@test.com", "123", organization_id=org_id)
    facade.login("user@test.com", "123")

    with pytest.raises(PermissionError):
        facade.require_same_organization("other-org-id")


def test_kernel_execute_in_organization():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    facade = PlatformKernelFacade(container=container)

    org_id = container.auth().create_organization("Acme")
    container.auth().register_user("user@test.com", "123", organization_id=org_id)
    facade.login("user@test.com", "123")

    def fn():
        return "ok"

    assert facade.execute_in_organization(org_id, fn) == "ok"


def test_kernel_check_plan_limit_bloqueia():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    facade = PlatformKernelFacade(container=container)

    org_id = container.auth().create_organization("Acme")
    container.auth().register_user("user@test.com", "123", organization_id=org_id)
    facade.login("user@test.com", "123")

    with pytest.raises(PermissionError):
        facade.check_plan_limit("users")


def test_kernel_execute_with_limit():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    facade = PlatformKernelFacade(container=container)

    org_id = container.auth().create_organization("Acme")
    container.auth().register_user("user@test.com", "123", organization_id=org_id)
    facade.login("user@test.com", "123")

    def fn():
        return "ok"

    assert facade.execute_with_limit("requests_per_day", fn) == "ok"


def test_kernel_upgrade_plan():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    facade = PlatformKernelFacade(container=container)

    org_id = container.auth().create_organization("Acme")
    container.auth().register_user(
        "owner@test.com", "123", organization_id=org_id, organization_role="owner"
    )
    facade.login("owner@test.com", "123")

    facade.upgrade_plan("pro")

    assert container.auth().get_organization_plan(org_id) == "pro"
