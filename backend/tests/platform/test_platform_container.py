import inspect

import pytest
from pydantic import ValidationError

from app.platform.bootstrap import (
    platform_bootstrap,
    platform_container,
    platform_container_factory,
    platform_read_models_compat,
    platform_read_models_validator,
)
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.bootstrap.platform_container_factory import build_default_platform_container
from app.platform.bootstrap.platform_service_catalog import PlatformServiceCatalog

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
    "events",
    "lifecycle",
    "capabilities",
    "features",
]


@pytest.mark.parametrize("service_name", _SERVICE_NAMES)
def test_container_resolve_preserva_identidade(service_name: str):
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)
    direct_instance = getattr(bootstrap, service_name)()

    assert container.resolve(service_name) is direct_instance


def test_container_resolve_health_retorna_exatamente_bootstrap_health():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    resolved = container.resolve("health")

    assert resolved is bootstrap.health()


def test_container_resolve_health_nao_reconstroi(monkeypatch):
    calls = {"count": 0}
    original = platform_bootstrap.build_default_platform_health_facade

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(platform_bootstrap, "build_default_platform_health_facade", _spy)

    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    container.resolve("health")
    container.resolve("health")
    container.exists("health")

    assert calls["count"] == 1


def test_container_health_retorna_exatamente_bootstrap_health():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    assert container.health() is bootstrap.health()


def test_health_chama_resolve_health_exatamente_uma_vez(monkeypatch):
    calls: list[str] = []
    original_resolve = PlatformContainer.resolve

    def _spy(self, name):
        calls.append(name)
        return original_resolve(self, name)

    monkeypatch.setattr(PlatformContainer, "resolve", _spy)

    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.health()

    assert calls == ["health"]


def test_health_nao_reconstroi(monkeypatch):
    calls = {"count": 0}
    original = platform_bootstrap.build_default_platform_health_facade

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(platform_bootstrap, "build_default_platform_health_facade", _spy)

    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    container.health()
    container.health()

    assert calls["count"] == 1


def test_container_events_retorna_exatamente_bootstrap_events():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    assert container.events() is bootstrap.events()


def test_events_chama_resolve_events_exatamente_uma_vez(monkeypatch):
    calls: list[str] = []
    original_resolve = PlatformContainer.resolve

    def _spy(self, name):
        calls.append(name)
        return original_resolve(self, name)

    monkeypatch.setattr(PlatformContainer, "resolve", _spy)

    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.events()

    assert calls == ["events"]


def test_events_nao_reconstroi(monkeypatch):
    calls = {"count": 0}
    original = platform_bootstrap.build_default_platform_events

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(platform_bootstrap, "build_default_platform_events", _spy)

    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    container.events()
    container.events()

    assert calls["count"] == 1


def test_container_lifecycle_retorna_exatamente_bootstrap_lifecycle():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    assert container.lifecycle() is bootstrap.lifecycle()


def test_lifecycle_chama_resolve_lifecycle_exatamente_uma_vez(monkeypatch):
    calls: list[str] = []
    original_resolve = PlatformContainer.resolve

    def _spy(self, name):
        calls.append(name)
        return original_resolve(self, name)

    monkeypatch.setattr(PlatformContainer, "resolve", _spy)

    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.lifecycle()

    assert calls == ["lifecycle"]


def test_lifecycle_nao_reconstroi(monkeypatch):
    calls = {"count": 0}
    original = platform_bootstrap.build_default_platform_lifecycle

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(platform_bootstrap, "build_default_platform_lifecycle", _spy)

    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    container.lifecycle()
    container.lifecycle()

    assert calls["count"] == 1


def test_container_capabilities_retorna_exatamente_bootstrap_capabilities():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    assert container.capabilities() is bootstrap.capabilities()


def test_capabilities_chama_resolve_capabilities_exatamente_uma_vez(monkeypatch):
    calls: list[str] = []
    original_resolve = PlatformContainer.resolve

    def _spy(self, name):
        calls.append(name)
        return original_resolve(self, name)

    monkeypatch.setattr(PlatformContainer, "resolve", _spy)

    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.capabilities()

    assert calls == ["capabilities"]


def test_capabilities_nao_reconstroi(monkeypatch):
    calls = {"count": 0}
    original = platform_bootstrap.build_default_platform_capabilities

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(platform_bootstrap, "build_default_platform_capabilities", _spy)

    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    container.capabilities()
    container.capabilities()

    assert calls["count"] == 1


def test_container_features_retorna_exatamente_bootstrap_features():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    assert container.features() is bootstrap.features()


def test_features_chama_resolve_features_exatamente_uma_vez(monkeypatch):
    calls: list[str] = []
    original_resolve = PlatformContainer.resolve

    def _spy(self, name):
        calls.append(name)
        return original_resolve(self, name)

    monkeypatch.setattr(PlatformContainer, "resolve", _spy)

    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.features()

    assert calls == ["features"]


def test_features_nao_reconstroi(monkeypatch):
    calls = {"count": 0}
    original = platform_bootstrap.build_default_platform_features

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(platform_bootstrap, "build_default_platform_features", _spy)

    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    container.features()
    container.features()

    assert calls["count"] == 1


def test_container_catalog_retorna_exatamente_bootstrap_catalog():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    assert container.catalog() is bootstrap.catalog()


def test_catalog_chama_bootstrap_catalog_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = PlatformBootstrap.catalog

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(PlatformBootstrap, "catalog", _spy)

    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.catalog()

    assert calls["count"] == 1


def test_catalog_nao_usa_resolve(monkeypatch):
    calls: list[str] = []
    original_resolve = PlatformContainer.resolve

    def _spy(self, name):
        calls.append(name)
        return original_resolve(self, name)

    monkeypatch.setattr(PlatformContainer, "resolve", _spy)

    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.catalog()

    assert calls == []


def test_catalog_nao_reconstroi(monkeypatch):
    calls = {"count": 0}
    original = platform_bootstrap.build_platform_service_catalog

    def _spy(*args, **kwargs):
        calls["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(platform_bootstrap, "build_platform_service_catalog", _spy)

    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    container.catalog()
    container.catalog()

    assert calls["count"] == 1


def test_container_catalog_identidade_preservada():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    assert container.catalog() is container.catalog()


def test_container_projections_retorna_dict():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert isinstance(container.projections(), dict)


def test_container_projections_contem_catalog():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    projections = container.projections()

    assert "catalog" in projections
    assert projections["catalog"] is bootstrap.catalog()


def test_container_projections_preserva_identidade():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert container.projections()["catalog"] is container.projections()["catalog"]


def test_projections_nao_usa_resolve(monkeypatch):
    calls: list[str] = []
    original_resolve = PlatformContainer.resolve

    def _spy(self, name):
        calls.append(name)
        return original_resolve(self, name)

    monkeypatch.setattr(PlatformContainer, "resolve", _spy)

    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.projections()

    assert calls == []


def test_projections_nao_usa_registry():
    source = inspect.getsource(PlatformContainer.projections)

    assert "registry" not in source.lower()
    assert "resolve" not in source.lower()


def test_projections_usa_build_projections():
    source = inspect.getsource(PlatformContainer.projections)

    assert "_build_projections" in source


def test_build_projections_retorna_dict():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert isinstance(container._build_projections(), dict)


def test_build_projections_contem_catalog():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    result = container._build_projections()

    assert "catalog" in result
    assert result["catalog"] is container.catalog()


def test_build_projections_preserva_identidade():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert container._build_projections()["catalog"] is container._build_projections()["catalog"]


def test_build_projections_nao_usa_resolve():
    source = inspect.getsource(PlatformContainer._build_projections)

    assert "resolve" not in source.lower()


def test_build_projections_nao_usa_registry():
    source = inspect.getsource(PlatformContainer._build_projections)

    assert "registry" not in source.lower()


def test_build_projections_contem_services():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    result = container._build_projections()

    assert "services" in result
    assert result["services"] == container.list()


def test_build_projections_services_preserva_ordem():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    result = container._build_projections()

    names_in_projection = [descriptor.name for descriptor in result["services"]]
    names_in_list = [descriptor.name for descriptor in container.list()]

    assert names_in_projection == names_in_list


def test_build_projections_services_preserva_identidade():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    result = container._build_projections()

    for projected, listed in zip(result["services"], container.list()):
        assert projected is listed


def test_build_projections_services_nao_usa_resolve():
    source = inspect.getsource(PlatformContainer._build_projections)

    assert "resolve" not in source.lower()


def test_build_projections_services_nao_usa_registry():
    source = inspect.getsource(PlatformContainer._build_projections)

    assert "registry" not in source.lower()


def test_build_projections_contem_service_names():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    result = container._build_projections()

    assert "service_names" in result
    assert result["service_names"] == tuple(d.name for d in container.list())


def test_build_projections_service_names_preserva_ordem():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    result = container._build_projections()

    assert list(result["service_names"]) == [d.name for d in container.list()]


def test_build_projections_service_names_corretos():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    result = container._build_projections()

    assert result["service_names"] == tuple(
        descriptor.name for descriptor in container.list()
    )


def test_build_projections_service_names_tipo_tuple():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    result = container._build_projections()

    assert isinstance(result["service_names"], tuple)


def test_build_projections_service_names_nao_usa_resolve():
    source = inspect.getsource(PlatformContainer._build_projections)

    assert "resolve" not in source.lower()


def test_build_projections_service_names_nao_usa_registry():
    source = inspect.getsource(PlatformContainer._build_projections)

    assert "registry" not in source.lower()


def test_build_projections_contem_service_map():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    result = container._build_projections()

    assert "service_map" in result


def test_build_projections_service_map_tipo_dict():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    result = container._build_projections()

    assert isinstance(result["service_map"], dict)


def test_build_projections_service_map_conteudo_correto():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    result = container._build_projections()
    service_map = result["service_map"]

    for descriptor in container.list():
        assert service_map[descriptor.name] is descriptor.instance


def test_build_projections_service_map_preserva_identidade():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    result = container._build_projections()
    service_map = result["service_map"]

    for descriptor in container.list():
        assert service_map[descriptor.name] is descriptor.instance


def test_build_projections_service_map_preserva_ordem():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    result = container._build_projections()

    assert list(result["service_map"].keys()) == [d.name for d in container.list()]


def test_build_projections_service_map_nao_usa_resolve():
    source = inspect.getsource(PlatformContainer._build_projections)

    assert "resolve" not in source.lower()


def test_build_projections_service_map_nao_usa_registry():
    source = inspect.getsource(PlatformContainer._build_projections)

    assert "registry" not in source.lower()


def test_projections_retorna_novo_dict():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert container.projections() is not container.projections()
    assert container.projections() == container.projections()


def test_container_service_names_retorna_tuple():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    result = container.service_names()

    assert isinstance(result, tuple)
    assert result == container.service_names_projection()


def test_container_service_names_preserva_ordem():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert list(container.service_names()) == [d.name for d in container.list()]


def test_container_service_names_igual_projections():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert container.service_names() == container.projections()["service_names"]


def test_container_service_names_nao_usa_resolve():
    source = inspect.getsource(PlatformContainer.service_names)

    assert "resolve" not in source.lower()


def test_container_service_names_nao_usa_registry():
    source = inspect.getsource(PlatformContainer.service_names)

    assert "registry" not in source.lower()


def test_service_names_delega_para_projection(monkeypatch):
    calls = {"count": 0}
    original = PlatformContainer.service_names_projection

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(PlatformContainer, "service_names_projection", _spy)

    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.service_names()

    assert calls["count"] == 1


def test_service_names_nao_usa_list():
    source = inspect.getsource(PlatformContainer.service_names)

    assert "list(" not in source


def test_service_names_sem_logica():
    source = inspect.getsource(PlatformContainer.service_names)

    assert "for " not in source
    assert "{" not in source


def test_container_service_map_retorna_dict():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    result = container.service_map()

    assert isinstance(result, dict)
    assert result == container.service_map_projection()


def test_container_service_map_conteudo_correto():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    service_map = container.service_map()

    for descriptor in container.list():
        assert service_map[descriptor.name] is descriptor.instance


def test_container_service_map_preserva_identidade():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    service_map = container.service_map()

    for descriptor in container.list():
        assert service_map[descriptor.name] is descriptor.instance


def test_container_service_map_igual_projections():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert container.service_map() == container.projections()["service_map"]


def test_container_service_map_nao_usa_resolve():
    source = inspect.getsource(PlatformContainer.service_map)

    assert "resolve" not in source.lower()


def test_container_service_map_nao_usa_registry():
    source = inspect.getsource(PlatformContainer.service_map)

    assert "registry" not in source.lower()


def test_service_map_projection_nao_usa_projections():
    source = inspect.getsource(PlatformContainer.service_map)

    assert "projections(" not in source


def test_service_map_delega_para_projection(monkeypatch):
    calls = {"count": 0}
    original = PlatformContainer.service_map_projection

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(PlatformContainer, "service_map_projection", _spy)

    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.service_map()

    assert calls["count"] == 1


def test_service_map_nao_usa_list():
    source = inspect.getsource(PlatformContainer.service_map)

    assert "self.list()" not in source


def test_service_map_sem_logica():
    source = inspect.getsource(PlatformContainer.service_map)

    assert "for " not in source


def test_service_map_projection_conteudo_correto():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    service_map = container.service_map()

    assert service_map == {d.name: d.instance for d in container.list()}


def test_service_map_projection_preserva_identidade():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    service_map = container.service_map()

    for descriptor in container.list():
        assert service_map[descriptor.name] is descriptor.instance


def test_service_map_projection_sem_delegacao():
    source = inspect.getsource(PlatformContainer.service_map)

    assert "self.service_names()" not in source
    assert "self.projections()" not in source
    assert "self.resolve(" not in source


def test_container_service_map_projection_retorna_dict():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert isinstance(container.service_map_projection(), dict)


def test_container_service_map_projection_conteudo_correto():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert container.service_map_projection() == {d.name: d.instance for d in container.list()}


def test_container_service_map_projection_preserva_identidade():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    service_map = container.service_map_projection()

    for descriptor in container.list():
        assert service_map[descriptor.name] is descriptor.instance


def test_container_service_map_projection_usa_list_diretamente():
    source = inspect.getsource(PlatformContainer.service_map_projection)

    assert "self.list()" in source


def test_container_service_map_projection_nao_usa_projections():
    source = inspect.getsource(PlatformContainer.service_map_projection)

    assert "projections(" not in source


def test_service_map_projection_nao_usa_resolve():
    source = inspect.getsource(PlatformContainer.service_map_projection)

    assert "resolve(" not in source


def test_container_service_map_projection_sem_delegacao():
    source = inspect.getsource(PlatformContainer.service_map_projection)

    assert "self.service_names()" not in source
    assert "self.service_map()" not in source
    assert "self.projections()" not in source
    assert "self.resolve(" not in source


def test_container_services_projection_retorna_list():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    result = container.services_projection()

    assert isinstance(result, list)
    assert result == container.list()


def test_container_services_projection_preserva_ordem():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    names_projected = [d.name for d in container.services_projection()]
    names_listed = [d.name for d in container.list()]

    assert names_projected == names_listed


def test_container_services_projection_preserva_identidade():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    for projected, listed in zip(container.services_projection(), container.list()):
        assert projected is listed


def test_container_services_projection_igual_projections():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert container.services_projection() == container.projections()["services"]


def test_services_projection_nao_usa_resolve():
    source = inspect.getsource(PlatformContainer.services_projection)

    assert "resolve" not in source.lower()


def test_services_projection_nao_usa_registry():
    source = inspect.getsource(PlatformContainer.services_projection)

    assert "registry" not in source.lower()


def test_services_projection_nao_usa_projections():
    source = inspect.getsource(PlatformContainer.services_projection)

    assert "projections(" not in source


def test_services_projection_nao_usa_resolve_ou_registry():
    source = inspect.getsource(PlatformContainer.services_projection)

    assert "resolve(" not in source
    assert "registry" not in source


def test_services_projection_usa_list_diretamente():
    source = inspect.getsource(PlatformContainer.services_projection)

    assert "self.list()" in source


def test_services_projection_preserva_identidade():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    for projected, listed in zip(container.services_projection(), container.list()):
        assert projected is listed


def test_services_projection_sem_delegacao():
    source = inspect.getsource(PlatformContainer.services_projection)

    assert "self.service_names()" not in source
    assert "self.service_map()" not in source
    assert "self.projections()" not in source
    assert "self.resolve(" not in source


def test_container_read_models_retorna_dict():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert isinstance(container.read_models(), dict)


def test_container_read_models_igual_projections():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert container.read_models() == container.projections()


def test_container_read_models_identidade_preservada():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert container.read_models()["catalog"] is container.read_models()["catalog"]


def test_read_models_nao_usa_resolve():
    source = inspect.getsource(PlatformContainer.read_models)

    assert "resolve" not in source.lower()


def test_read_models_nao_usa_registry():
    source = inspect.getsource(PlatformContainer.read_models)

    assert "registry" not in source.lower()


def test_read_models_tipo_typed_dict():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    rm = container.read_models()

    assert isinstance(rm, dict)


def test_read_models_contem_chaves_esperadas():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    rm = container.read_models()

    assert "catalog" in rm
    assert "services" in rm
    assert "service_names" in rm
    assert "service_map" in rm


def test_read_models_tipos_corretos():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    rm = container.read_models()

    assert isinstance(rm["catalog"], PlatformServiceCatalog)
    assert isinstance(rm["services"], list)
    assert isinstance(rm["service_names"], tuple)
    assert isinstance(rm["service_map"], dict)


def test_read_models_validated_retorna_dict():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert isinstance(container.read_models_validated(), dict)


def test_read_models_validated_igual_read_models():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert container.read_models_validated() == container.read_models()


def test_read_models_validated_chama_validator(monkeypatch):
    calls = {"count": 0}
    original = platform_read_models_validator.validate_read_models

    def _spy(data):
        calls["count"] += 1
        return original(data)

    monkeypatch.setattr(platform_read_models_validator, "validate_read_models", _spy)

    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.read_models_validated()

    assert calls["count"] == 1


def test_read_models_validated_preserva_identidade_interna():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    assert container.read_models_validated()["catalog"] is bootstrap.catalog()


def test_read_models_validated_erro_quando_faltam_chaves(monkeypatch):
    monkeypatch.setattr(PlatformContainer, "read_models", lambda self: {})

    container = PlatformContainer(bootstrap=PlatformBootstrap())

    with pytest.raises(ValueError):
        container.read_models_validated()


def test_read_models_version_retorna_string():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert isinstance(container.read_models_version(), str)


def test_read_models_version_valor_esperado():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert container.read_models_version() == "1.0.0"


def test_read_models_version_constante():
    from app.platform.bootstrap.platform_read_models_version import READ_MODELS_VERSION

    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert container.read_models_version() == READ_MODELS_VERSION


def test_read_models_version_nao_depende_de_projections():
    source = inspect.getsource(PlatformContainer.read_models_version)

    assert "projections" not in source
    assert "read_models(" not in source


def test_read_models_version_idempotente():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert container.read_models_version() == container.read_models_version()


def test_read_models_v1_retorna_dict():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert isinstance(container.read_models_v1(), dict)


def test_read_models_v1_igual_read_models():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert container.read_models_v1() == container.read_models()


def test_read_models_v1_chama_compat_layer(monkeypatch):
    calls = {"count": 0}
    original = platform_read_models_compat.get_read_models_v1

    def _spy(data):
        calls["count"] += 1
        return original(data)

    monkeypatch.setattr(platform_read_models_compat, "get_read_models_v1", _spy)

    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.read_models_v1()

    assert calls["count"] == 1


def test_read_models_v1_preserva_identidade_interna():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    assert container.read_models_v1()["catalog"] is bootstrap.catalog()


def test_container_catalog_projection_retorna_catalog():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    assert container.catalog_projection() is bootstrap.catalog()


def test_container_catalog_projection_identidade_preservada():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    first = container.catalog_projection()
    second = container.catalog_projection()

    assert first is second


def test_catalog_projection_nao_usa_projections():
    source = inspect.getsource(PlatformContainer.catalog_projection)

    assert "projections(" not in source


def test_catalog_projection_nao_usa_resolve_ou_registry():
    source = inspect.getsource(PlatformContainer.catalog_projection)

    assert "resolve(" not in source
    assert "registry" not in source


def test_container_service_names_projection_retorna_tuple():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    result = container.service_names_projection()

    assert isinstance(result, tuple)
    assert result == tuple(descriptor.name for descriptor in container.list())


def test_container_service_names_projection_preserva_ordem():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    expected = tuple(d.name for d in container.list())

    assert container.service_names_projection() == expected


def test_container_service_names_projection_conteudo_correto():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    names = container.service_names_projection()

    assert all(isinstance(n, str) for n in names)
    assert len(names) == len(container.list())


def test_service_names_projection_nao_usa_projections():
    source = inspect.getsource(PlatformContainer.service_names_projection)

    assert "projections(" not in source


def test_service_names_projection_nao_usa_resolve_ou_registry():
    source = inspect.getsource(PlatformContainer.service_names_projection)

    assert "resolve(" not in source
    assert "registry" not in source


def test_service_names_projection_nao_usa_service_names():
    source = inspect.getsource(PlatformContainer.service_names_projection)

    assert "service_names(" not in source


def test_service_names_projection_usa_list_diretamente():
    source = inspect.getsource(PlatformContainer.service_names_projection)

    assert "self.list()" in source


def test_service_names_projection_independente_de_projections():
    source = inspect.getsource(PlatformContainer.service_names_projection)

    assert "projections(" not in source


def test_service_names_projection_sem_delegacao():
    source = inspect.getsource(PlatformContainer.service_names_projection)

    assert "self.service_names()" not in source
    assert "self.projections()" not in source
    assert "self.resolve(" not in source


def test_resolve_inexistente_levanta_key_error():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    with pytest.raises(KeyError):
        container.resolve("does_not_exist")


def test_exists():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    for service_name in _SERVICE_NAMES:
        assert container.exists(service_name) is True
    assert container.exists("does_not_exist") is False


def test_list():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    names = {descriptor.name for descriptor in container.list()}

    assert names == set(_SERVICE_NAMES)


def test_imutabilidade_rejects_attribute_assignment():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    with pytest.raises(ValidationError):
        container.bootstrap = PlatformBootstrap()


def test_injecao_uses_exactly_the_bootstrap_provided():
    bootstrap = PlatformBootstrap()

    container = PlatformContainer(bootstrap=bootstrap)

    assert container.bootstrap is bootstrap


def test_container_utiliza_exclusivamente_bootstrap_resolver():
    source = inspect.getsource(platform_container)

    assert "bootstrap.resolver()" in source


def test_bootstrap_chamado_exatamente_uma_vez(monkeypatch):
    from app.platform.bootstrap import platform_bootstrap_factory

    calls = {"count": 0}
    original = platform_bootstrap_factory.build_default_platform_bootstrap

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(
        platform_container_factory, "build_default_platform_bootstrap", _spy
    )

    build_default_platform_container()

    assert calls["count"] == 1


def test_resolver_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = platform_bootstrap.build_default_platform_service_resolver

    def _spy(*args, **kwargs):
        calls["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(platform_bootstrap, "build_default_platform_service_resolver", _spy)

    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    container.resolve("runtime")
    container.exists("operations")
    container.list()
    container.resolve("command_bus")

    assert calls["count"] == 1


def test_platform_container_conhece_apenas_platform_bootstrap():
    source = inspect.getsource(platform_container)

    assert "PlatformBootstrap" in source
    assert "PlatformServiceRegistry" not in source
    assert "PlatformServiceResolver" not in source
    assert "PlatformServiceDescriptor" not in source


def test_container_nenhuma_factory():
    source = inspect.getsource(platform_container)

    assert "factory" not in source.lower()
    assert "build_default" not in source


def test_container_nenhum_engine():
    source = inspect.getsource(platform_container)

    assert "app.runtime" not in source
    assert "app.operations" not in source


def test_container_nenhum_service_concreto():
    source = inspect.getsource(platform_container)

    assert "CommandBusService" not in source
    assert "QueryBusService" not in source
    assert "PublicUseCaseService" not in source
    assert "PresentationFacade" not in source
    assert "PlatformInterface" not in source
    assert "PlatformExecutionOrchestrator" not in source


def test_container_nenhuma_instanciacao_direta():
    source = inspect.getsource(platform_container)

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


def test_factory_retorna_platform_container():
    container = build_default_platform_container()

    assert isinstance(container, PlatformContainer)


def test_container_nenhuma_referencia_a_componentes_concretos_de_health():
    source = inspect.getsource(platform_container)

    assert "PlatformHealthFacade" not in source
    assert "HealthCoordinator" not in source
    assert "HealthMonitor" not in source
    assert "HealthReportService" not in source
    assert "HealthExecutor" not in source
    assert "HealthManager" not in source


def test_container_nenhuma_referencia_a_componentes_concretos_de_events():
    source = inspect.getsource(platform_container)

    assert "PlatformEvents" not in source
    assert "PlatformEventExecutor" not in source
    assert "PlatformEventManager" not in source
    assert "EventRegistry" not in source
    assert "PlatformEvent" not in source


def test_container_nenhuma_referencia_a_componentes_concretos_de_lifecycle():
    source = inspect.getsource(platform_container)

    assert "PlatformLifecycle" not in source
    assert "LifecycleExecutor" not in source
    assert "LifecycleManager" not in source
    assert "LifecycleStarter" not in source
    assert "LifecycleStopper" not in source
    assert "LifecycleParticipant" not in source
    assert "LifecycleParticipantRegistry" not in source


def test_container_nenhuma_referencia_a_componentes_concretos_de_capabilities():
    source = inspect.getsource(platform_container)

    assert "PlatformCapabilities" not in source
    assert "CapabilityExecutor" not in source
    assert "CapabilityManager" not in source
    assert "CapabilityRegistry" not in source
    assert "Capability" not in source


def test_container_nenhuma_referencia_a_componentes_concretos_de_features():
    source = inspect.getsource(platform_container)

    assert "PlatformFeatures" not in source
    assert "FeatureExecutor" not in source
    assert "FeatureManager" not in source
    assert "FeatureRegistry" not in source
    assert "Feature" not in source


def test_container_nenhuma_referencia_a_componentes_concretos_de_catalog():
    source = inspect.getsource(platform_container)

    assert "PlatformServiceCatalog" not in source
    assert "PlatformServiceRegistry" not in source
    assert "PlatformServiceResolver" not in source
    assert 'resolve("catalog")' not in source
    assert "bootstrap.catalog()" in source


def test_catalog_nao_e_resolvido_via_resolve():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    with pytest.raises(KeyError):
        container.resolve("catalog")


def test_catalog_nao_aparece_em_exists_nem_list():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert container.exists("catalog") is False
    assert "catalog" not in {descriptor.name for descriptor in container.list()}


def test_catalog_nao_esta_em_service_names():
    assert "catalog" not in _SERVICE_NAMES


def test_container_metodos_usam_fonte_correta():
    catalog_projection_source = inspect.getsource(PlatformContainer.catalog_projection)
    assert "self.catalog(" in catalog_projection_source

    services_projection_source = inspect.getsource(PlatformContainer.services_projection)
    assert "self.list(" in services_projection_source

    service_names_projection_source = inspect.getsource(
        PlatformContainer.service_names_projection
    )
    assert "self.list(" in service_names_projection_source

    service_map_projection_source = inspect.getsource(PlatformContainer.service_map_projection)
    assert "self.list(" in service_map_projection_source

    service_names_source = inspect.getsource(PlatformContainer.service_names)
    assert "self.service_names_projection(" in service_names_source

    service_map_source = inspect.getsource(PlatformContainer.service_map)
    assert "self.service_map_projection(" in service_map_source


def test_container_nao_usa_projections_indiretamente():
    for method_name in (
        "catalog_projection",
        "services_projection",
        "service_names_projection",
        "service_map_projection",
        "service_names",
        "service_map",
    ):
        source = inspect.getsource(getattr(PlatformContainer, method_name))

        assert "projections(" not in source


def test_container_sem_logica():
    for method_name in ("catalog_projection", "service_names", "service_map"):
        source = inspect.getsource(getattr(PlatformContainer, method_name))

        assert "for " not in source
        assert "if " not in source
        assert "dict(" not in source
        assert "tuple(" not in source
        assert "set(" not in source

    services_projection_source = inspect.getsource(PlatformContainer.services_projection)
    assert "for " not in services_projection_source
    assert "if " not in services_projection_source
    assert "dict(" not in services_projection_source
    assert "set(" not in services_projection_source

    service_map_projection_source = inspect.getsource(PlatformContainer.service_map_projection)
    assert "if " not in service_map_projection_source
    assert "dict(" not in service_map_projection_source
    assert "tuple(" not in service_map_projection_source
    assert "set(" not in service_map_projection_source

    service_names_projection_source = inspect.getsource(
        PlatformContainer.service_names_projection
    )
    assert "if " not in service_names_projection_source
    assert "dict(" not in service_names_projection_source
    assert "set(" not in service_names_projection_source


def test_container_nao_usa_resolve_ou_registry_em_nenhum_metodo():
    for method_name in (
        "catalog_projection",
        "services_projection",
        "service_names_projection",
        "service_map_projection",
        "service_names",
        "service_map",
    ):
        source = inspect.getsource(getattr(PlatformContainer, method_name))

        assert "resolve(" not in source
        assert "registry" not in source


def test_projections_continua_agregador():
    source = inspect.getsource(PlatformContainer.projections)

    assert "_build_projections(" in source
    assert "self.list(" not in source
    assert "self.catalog(" not in source


def test_projections_services_igual_list():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert container.projections()["services"] == container.list()


def test_projections_service_names_igual_list():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    expected = tuple(descriptor.name for descriptor in container.list())

    assert container.projections()["service_names"] == expected


def test_projections_service_map_igual_list():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    expected = {descriptor.name: descriptor.instance for descriptor in container.list()}

    assert container.projections()["service_map"] == expected


def test_projections_catalog_igual_catalog():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert container.projections()["catalog"] is container.catalog()


def test_projections_nao_transforma_dados():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    projections = container.projections()
    listed = container.list()

    services_names = [d.name for d in projections["services"]]
    listed_names = [d.name for d in listed]
    assert services_names == listed_names

    service_names_names = list(projections["service_names"])
    assert service_names_names == listed_names

    for descriptor in listed:
        assert projections["service_map"][descriptor.name] is descriptor.instance


def test_build_projections_nao_usa_projections():
    source = inspect.getsource(PlatformContainer._build_projections)
    body = source.split("\n", 1)[1]

    assert "projections(" not in body


def test_build_projections_usa_fontes_diretas():
    source = inspect.getsource(PlatformContainer._build_projections)

    assert "self.list(" in source
    assert "self.catalog(" in source
    assert "service_names(" not in source
    assert "service_map(" not in source


def test_read_models_v1_usa_apply_v1(monkeypatch):
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    called = {"count": 0}

    def fake(data):
        called["count"] += 1
        return data

    monkeypatch.setattr(
        "app.platform.bootstrap.platform_read_models_compat._apply_v1",
        fake,
    )

    container.read_models_v1()

    assert called["count"] == 1


def test_apply_v1_retorna_mesmo_objeto():
    from app.platform.bootstrap.platform_read_models_compat import _apply_v1

    data = {"a": 1}

    result = _apply_v1(data)

    assert result is data


def test_apply_v1_sem_logica():
    from app.platform.bootstrap.platform_read_models_compat import _apply_v1

    source = inspect.getsource(_apply_v1)

    assert "return data" in source
    assert "for " not in source
    assert "if " not in source


def test_read_models_v1_version_retorna_string():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    version = container.read_models_v1_version()

    assert isinstance(version, str)


def test_read_models_v1_version_igual_read_models_version():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    assert container.read_models_v1_version() == container.read_models_version()


def test_read_models_v2_igual_v1():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    assert container.read_models_v2() == container.read_models_v1()


def test_read_models_v2_conteudo_identico_a_v1():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    v2 = container.read_models_v2()

    assert v2["catalog"] is bootstrap.catalog()
    assert set(v2.keys()) == {"catalog", "services", "service_names", "service_map"}


def test_read_models_v2_sem_logica():
    source = inspect.getsource(PlatformContainer.read_models_v2)

    assert "for " not in source
    assert "if " not in source


def test_read_models_v2_usa_apply_v2():
    from app.platform.bootstrap import platform_read_models_compat

    source = inspect.getsource(platform_read_models_compat.get_read_models_v2)

    assert "_apply_v2" in source
    assert "_apply_v1" not in source


def test_read_models_v2_igual_read_models():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    assert container.read_models_v2() == container.read_models()


def test_read_models_v2_catalog_identidade_preservada():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    v2 = container.read_models_v2()
    base = container.read_models()

    assert v2["catalog"] is base["catalog"]


def test_read_models_v2_registrado_como_v2():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    data = container.read_models_v2()

    assert container._is_v2(data) is True


def test_read_models_v1_nao_registrado_como_v2():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    data = container.read_models_v1()

    assert container._is_v2(data) is False


def test_v2_registry_limitado():
    from app.platform.bootstrap.platform_read_models_compat import _V2_MAX

    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    for _ in range(_V2_MAX + 10):
        container.read_models_v2()

    assert len(container._v2_registry) <= _V2_MAX


def test_is_v2_funciona():
    bootstrap = PlatformBootstrap()
    container = PlatformContainer(bootstrap=bootstrap)

    v2 = container.read_models_v2()
    v1 = container.read_models_v1()

    assert container._is_v2(v2) is True
    assert container._is_v2(v1) is False


def test_v2_registry_isolado_por_instancia():
    bootstrap = PlatformBootstrap()
    container_a = PlatformContainer(bootstrap=bootstrap)
    container_b = PlatformContainer(bootstrap=bootstrap)

    data_a = container_a.read_models_v2()

    assert container_a._is_v2(data_a) is True
    assert container_b._is_v2(data_a) is False


def test_read_models_v2_passa_por_transform():
    from app.platform.bootstrap import platform_read_models_compat as compat

    called = {"flag": False}

    def fake_transform(data):
        called["flag"] = True
        return data

    original = compat._transform_v2
    compat._transform_v2 = fake_transform

    try:
        container = PlatformContainer(bootstrap=PlatformBootstrap())
        container.read_models_v2()
        assert called["flag"] is True
    finally:
        compat._transform_v2 = original


def test_transform_v2_nao_altera_payload():
    from app.platform.bootstrap.platform_read_models_compat import _transform_v2

    data = {"a": 1}
    result = _transform_v2(data)

    assert result == data
    assert result is not data


def test_apply_v2_usa_transform():
    from app.platform.bootstrap import platform_read_models_compat as compat

    called = {"flag": False}

    def fake_transform(data):
        called["flag"] = True
        return data

    original = compat._transform_v2
    compat._transform_v2 = fake_transform

    try:
        registry = {}
        counter = [0]
        compat._apply_v2({}, registry, counter)
        assert called["flag"] is True
    finally:
        compat._transform_v2 = original


def test_transform_v2_existe_e_execucao_ok():
    from app.platform.bootstrap.platform_read_models_compat import _transform_v2

    data = {"x": 1}
    result = _transform_v2(data)

    assert result == data


def test_read_models_v2_continua_igual_read_models():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    v2 = container.read_models_v2()
    base = container.read_models()

    assert v2 == base


def test_transform_v2_ponto_unico_de_transformacao():
    from app.platform.bootstrap import platform_read_models_compat as compat

    calls = {"count": 0}

    def spy(data):
        calls["count"] += 1
        return data

    original = compat._transform_v2
    compat._transform_v2 = spy

    try:
        container = PlatformContainer(bootstrap=PlatformBootstrap())
        container.read_models_v2()
        assert calls["count"] == 1
    finally:
        compat._transform_v2 = original


def test_v2_meta_disponivel():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    data = container.read_models_v2()
    meta = container._get_v2_meta(data)

    assert meta is not None
    assert meta["version"] == "v2"
    assert meta["processed"] is True


def test_v2_meta_nao_afeta_payload():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    v2 = container.read_models_v2()
    base = container.read_models()

    assert v2 == base
    assert "__meta__" not in v2
    assert container._get_v2_meta(v2) is not None


def test_v2_meta_isolado_por_objeto():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    v2_a = container.read_models_v2()
    v2_b = container.read_models_v2()

    assert container._get_v2_meta(v2_a) is not None
    assert container._get_v2_meta(v2_b) is not None
    assert v2_a is not v2_b


def test_v2_meta_isolado_por_instancia():
    c1 = PlatformContainer(bootstrap=PlatformBootstrap())
    c2 = PlatformContainer(bootstrap=PlatformBootstrap())

    d1 = c1.read_models_v2()
    d2 = c2.read_models_v2()

    assert c1._get_v2_meta(d1) is not None
    assert c2._get_v2_meta(d2) is not None

    assert c1._get_v2_meta(d1) is not c2._get_v2_meta(d2)


def test_v2_meta_limitado():
    from app.platform.bootstrap.platform_read_models_compat import _V2_MAX

    c = PlatformContainer(bootstrap=PlatformBootstrap())

    for _ in range(_V2_MAX + 100):
        c.read_models_v2()

    assert len(c._v2_meta) <= _V2_MAX


def test_v2_meta_consistente():
    c = PlatformContainer(bootstrap=PlatformBootstrap())

    d = c.read_models_v2()
    meta = c._get_v2_meta(d)

    assert meta["version"] == "v2"
    assert meta["processed"] is True


def test_v2_transform_normaliza_chaves():
    c = PlatformContainer(bootstrap=PlatformBootstrap())

    base = c.read_models()
    v2 = c.read_models_v2()

    for k in base.keys():
        assert k.lower() in v2


def test_v2_transform_nao_perde_dados():
    c = PlatformContainer(bootstrap=PlatformBootstrap())

    base = c.read_models()
    v2 = c.read_models_v2()

    assert len(base) == len(v2)


def test_v2_transform_meta_indica_normalizacao():
    c = PlatformContainer(bootstrap=PlatformBootstrap())

    d = c.read_models_v2()
    meta = c._get_v2_meta(d)

    assert meta["normalized"] is True


def test_compare_v1_v2_sem_diferenca():
    c = PlatformContainer(bootstrap=PlatformBootstrap())

    result = c.compare_read_models_versions()

    assert result["same_keys"] is True
    assert result["same_length"] is True
    assert result["differences"] == []


def test_compare_v1_v2_detecta_diferenca():
    from app.platform.bootstrap import platform_read_models_compat as compat

    original = compat._transform_v2

    def fake(data):
        new = dict(data)
        new["extra"] = 123
        return new

    compat._transform_v2 = fake

    try:
        c = PlatformContainer(bootstrap=PlatformBootstrap())
        result = c.compare_read_models_versions()

        assert result["same_keys"] is False
        assert "extra" in result["differences"]
    finally:
        compat._transform_v2 = original


def test_login_retorna_sessao():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    c.auth().register_user("user@example.com", "correct-horse-battery-staple")

    session = c.login("user@example.com", "correct-horse-battery-staple")

    assert session is not None
    assert "token" in session
    assert session["email"] == "user@example.com"


def test_login_invalido_retorna_none():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    c.auth().register_user("user@example.com", "correct-horse-battery-staple")

    session = c.login("user@example.com", "wrong-password")

    assert session is None


def test_login_usuario_inexistente_retorna_none():
    c = PlatformContainer(bootstrap=PlatformBootstrap())

    session = c.login("ghost@example.com", "whatever")

    assert session is None


def test_current_user_apos_login():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    c.auth().register_user("user@example.com", "correct-horse-battery-staple")

    c.login("user@example.com", "correct-horse-battery-staple")
    user = c.current_user()

    assert user is not None
    assert user["email"] == "user@example.com"


def test_current_user_sem_login_retorna_none():
    c = PlatformContainer(bootstrap=PlatformBootstrap())

    assert c.current_user() is None


def test_logout_remove_sessao():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    c.auth().register_user("user@example.com", "correct-horse-battery-staple")

    session = c.login("user@example.com", "correct-horse-battery-staple")
    token = session["token"]

    c.logout()

    assert c.current_user() is None
    assert c.auth().is_authenticated(token) is False


def test_auth_session_lookup():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    c.auth().register_user("user@example.com", "correct-horse-battery-staple")

    session = c.login("user@example.com", "correct-horse-battery-staple")
    token = session["token"]

    found = c.auth().get_session(token)

    assert found["email"] == "user@example.com"


def test_require_auth_funciona():
    c = PlatformContainer(bootstrap=PlatformBootstrap())

    c.auth().register_user("user@example.com", "correct-horse-battery-staple")
    c.login("user@example.com", "correct-horse-battery-staple")

    user = c.require_auth()

    assert user["email"] == "user@example.com"


def test_require_auth_bloqueia():
    c = PlatformContainer(bootstrap=PlatformBootstrap())

    with pytest.raises(PermissionError):
        c.require_auth()


def test_current_user_email_ok():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    c.auth().register_user("user@test.com", "123")

    c.login("user@test.com", "123")

    assert c.current_user_email() == "user@test.com"


def test_current_user_email_sem_login():
    c = PlatformContainer(bootstrap=PlatformBootstrap())

    with pytest.raises(PermissionError):
        c.current_user_email()


def test_execute_authenticated_funciona():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    c.auth().register_user("user@test.com", "123")

    c.login("user@test.com", "123")

    def acao():
        return "ok"

    result = c.execute_authenticated(acao)

    assert result == "ok"


def test_execute_authenticated_bloqueia():
    c = PlatformContainer(bootstrap=PlatformBootstrap())

    def acao():
        return "ok"

    with pytest.raises(PermissionError):
        c.execute_authenticated(acao)


def test_execute_authenticated_repassa_argumentos():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    c.auth().register_user("user@test.com", "123")

    c.login("user@test.com", "123")

    def soma(a, b, fator=1):
        return (a + b) * fator

    result = c.execute_authenticated(soma, 2, 3, fator=10)

    assert result == 50


def test_user_role_default():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    c.auth().register_user("user@test.com", "123")

    c.login("user@test.com", "123")

    assert c.current_user_role() == "user"


def test_admin_role():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    c.auth().register_user("admin@test.com", "123", role="admin")

    c.login("admin@test.com", "123")

    assert c.current_user_role() == "admin"


def test_current_user_role_sem_login():
    c = PlatformContainer(bootstrap=PlatformBootstrap())

    with pytest.raises(PermissionError):
        c.current_user_role()


def test_require_role_ok():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    c.auth().register_user("admin@test.com", "123", role="admin")

    c.login("admin@test.com", "123")

    c.require_role("admin")


def test_require_role_bloqueia():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    c.auth().register_user("user@test.com", "123", role="user")

    c.login("user@test.com", "123")

    with pytest.raises(PermissionError):
        c.require_role("admin")


def test_require_role_bloqueia_sem_login():
    c = PlatformContainer(bootstrap=PlatformBootstrap())

    with pytest.raises(PermissionError):
        c.require_role("admin")


def test_execute_with_role():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    c.auth().register_user("admin@test.com", "123", role="admin")

    c.login("admin@test.com", "123")

    def acao():
        return "ok"

    assert c.execute_with_role("admin", acao) == "ok"


def test_execute_with_role_bloqueia():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    c.auth().register_user("user@test.com", "123", role="user")

    c.login("user@test.com", "123")

    def acao():
        return "ok"

    with pytest.raises(PermissionError):
        c.execute_with_role("admin", acao)


def test_execute_secure_apenas_auth():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    c.auth().register_user("user@test.com", "123")
    c.login("user@test.com", "123")

    def fn():
        return "ok"

    assert c.execute_secure(fn) == "ok"


def test_execute_secure_com_role():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    c.auth().register_user("admin@test.com", "123", role="admin")
    c.login("admin@test.com", "123")

    def fn():
        return "admin_ok"

    assert c.execute_secure(fn, role="admin") == "admin_ok"


def test_execute_secure_bloqueia_sem_login():
    c = PlatformContainer(bootstrap=PlatformBootstrap())

    def fn():
        return "fail"

    with pytest.raises(PermissionError):
        c.execute_secure(fn)


def test_execute_secure_bloqueia_role_incorreta():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    c.auth().register_user("user@test.com", "123", role="user")
    c.login("user@test.com", "123")

    def fn():
        return "fail"

    with pytest.raises(PermissionError):
        c.execute_secure(fn, role="admin")


def test_execute_secure_repassa_argumentos():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    c.auth().register_user("user@test.com", "123")
    c.login("user@test.com", "123")

    def soma(a, b, fator=1):
        return (a + b) * fator

    assert c.execute_secure(soma, 2, 3, fator=10) == 50


def test_requires_auth_decorator_funciona():
    from app.platform.auth.platform_auth_decorators import requires_auth

    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("user@test.com", "123")
    container.login("user@test.com", "123")

    @requires_auth(lambda: container)
    def fn():
        return "ok"

    assert fn() == "ok"


def test_requires_auth_decorator_bloqueia():
    from app.platform.auth.platform_auth_decorators import requires_auth

    container = PlatformContainer(bootstrap=PlatformBootstrap())

    @requires_auth(lambda: container)
    def fn():
        return "fail"

    with pytest.raises(PermissionError):
        fn()


def test_requires_role_decorator_funciona():
    from app.platform.auth.platform_auth_decorators import requires_role

    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("admin@test.com", "123", role="admin")
    container.login("admin@test.com", "123")

    @requires_role(lambda: container, "admin")
    def fn():
        return "admin_ok"

    assert fn() == "admin_ok"


def test_requires_role_decorator_bloqueia():
    from app.platform.auth.platform_auth_decorators import requires_role

    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("user@test.com", "123", role="user")
    container.login("user@test.com", "123")

    @requires_role(lambda: container, "admin")
    def fn():
        return "fail"

    with pytest.raises(PermissionError):
        fn()


def test_requires_auth_decorator_preserva_metadata():
    from app.platform.auth.platform_auth_decorators import requires_auth

    container = PlatformContainer(bootstrap=PlatformBootstrap())

    @requires_auth(lambda: container)
    def fn():
        """docstring de fn"""
        return "ok"

    assert fn.__name__ == "fn"
    assert fn.__doc__ == "docstring de fn"


def test_permission_ok():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    auth = container.auth()

    auth.register_user("user@test.com", "123", permissions=["campaign:create"])
    container.login("user@test.com", "123")

    container.require_permission("campaign:create")


def test_permission_bloqueia():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    auth = container.auth()

    auth.register_user("user@test.com", "123", permissions=[])
    container.login("user@test.com", "123")

    with pytest.raises(PermissionError):
        container.require_permission("campaign:create")


def test_permission_bloqueia_sem_login():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    with pytest.raises(PermissionError):
        container.require_permission("campaign:create")


def test_current_user_permissions_padrao_vazio():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    auth = container.auth()

    auth.register_user("user@test.com", "123")
    container.login("user@test.com", "123")

    assert container.current_user_permissions() == []


def test_execute_with_permission():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    auth = container.auth()

    auth.register_user("user@test.com", "123", permissions=["x"])
    container.login("user@test.com", "123")

    def fn():
        return "ok"

    assert container.execute_with_permission("x", fn) == "ok"


def test_execute_with_permission_bloqueia():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    auth = container.auth()

    auth.register_user("user@test.com", "123", permissions=[])
    container.login("user@test.com", "123")

    def fn():
        return "ok"

    with pytest.raises(PermissionError):
        container.execute_with_permission("x", fn)


def test_requires_permission_decorator_funciona():
    from app.platform.auth.platform_auth_decorators import requires_permission

    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("user@test.com", "123", permissions=["x"])
    container.login("user@test.com", "123")

    @requires_permission(lambda: container, "x")
    def fn():
        return "ok"

    assert fn() == "ok"


def test_requires_permission_decorator_bloqueia():
    from app.platform.auth.platform_auth_decorators import requires_permission

    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("user@test.com", "123", permissions=[])
    container.login("user@test.com", "123")

    @requires_permission(lambda: container, "x")
    def fn():
        return "ok"

    with pytest.raises(PermissionError):
        fn()


def test_current_organization_id_apos_login():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    auth = c.auth()
    org_id = auth.create_organization("Acme")

    auth.register_user("user@test.com", "123", organization_id=org_id)
    c.login("user@test.com", "123")

    assert c.current_organization_id() == org_id


def test_current_organization_id_sem_login():
    c = PlatformContainer(bootstrap=PlatformBootstrap())

    with pytest.raises(PermissionError):
        c.current_organization_id()


def test_require_same_organization_permite_mesma_org():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    auth = c.auth()
    org_id = auth.create_organization("Acme")

    auth.register_user("user@test.com", "123", organization_id=org_id)
    c.login("user@test.com", "123")

    c.require_same_organization(org_id)


def test_require_same_organization_bloqueia_org_diferente():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    auth = c.auth()
    org_id = auth.create_organization("Acme")

    auth.register_user("user@test.com", "123", organization_id=org_id)
    c.login("user@test.com", "123")

    with pytest.raises(PermissionError):
        c.require_same_organization("other-org-id")


def test_execute_in_organization_funciona():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    auth = c.auth()
    org_id = auth.create_organization("Acme")

    auth.register_user("user@test.com", "123", organization_id=org_id)
    c.login("user@test.com", "123")

    def fn():
        return "ok"

    assert c.execute_in_organization(org_id, fn) == "ok"


def test_execute_in_organization_bloqueia_org_diferente():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    auth = c.auth()
    org_id = auth.create_organization("Acme")

    auth.register_user("user@test.com", "123", organization_id=org_id)
    c.login("user@test.com", "123")

    def fn():
        return "ok"

    with pytest.raises(PermissionError):
        c.execute_in_organization("other-org-id", fn)


def test_usuarios_em_organizacoes_diferentes_nao_compartilham_acesso():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    auth = c.auth()

    org_a = auth.create_organization("Org A")
    org_b = auth.create_organization("Org B")

    auth.register_user("a@test.com", "123", organization_id=org_a)
    auth.register_user("b@test.com", "123", organization_id=org_b)

    c.login("a@test.com", "123")
    assert c.current_organization_id() == org_a

    with pytest.raises(PermissionError):
        c.require_same_organization(org_b)


def test_dois_usuarios_na_mesma_org_compartilham_acesso():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    auth = c.auth()
    org_id = auth.create_organization("Acme")

    auth.register_user("a@test.com", "123", organization_id=org_id)
    auth.register_user("b@test.com", "123", organization_id=org_id)

    c.login("a@test.com", "123")
    c.require_same_organization(org_id)

    c.logout()

    c.login("b@test.com", "123")
    c.require_same_organization(org_id)


def test_requires_organization_decorator_funciona():
    from app.platform.auth.platform_auth_decorators import requires_organization

    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("user@test.com", "123")
    container.login("user@test.com", "123")

    @requires_organization(lambda: container)
    def fn():
        return "ok"

    assert fn() == "ok"


def test_requires_organization_decorator_bloqueia_sem_login():
    from app.platform.auth.platform_auth_decorators import requires_organization

    container = PlatformContainer(bootstrap=PlatformBootstrap())

    @requires_organization(lambda: container)
    def fn():
        return "ok"

    with pytest.raises(PermissionError):
        fn()


def test_requires_same_organization_decorator_funciona():
    from app.platform.auth.platform_auth_decorators import requires_same_organization

    container = PlatformContainer(bootstrap=PlatformBootstrap())
    auth = container.auth()
    org_id = auth.create_organization("Acme")

    auth.register_user("user@test.com", "123", organization_id=org_id)
    container.login("user@test.com", "123")

    @requires_same_organization(lambda: container, lambda: org_id)
    def fn():
        return "ok"

    assert fn() == "ok"


def test_requires_same_organization_decorator_bloqueia():
    from app.platform.auth.platform_auth_decorators import requires_same_organization

    container = PlatformContainer(bootstrap=PlatformBootstrap())
    auth = container.auth()
    org_id = auth.create_organization("Acme")

    auth.register_user("user@test.com", "123", organization_id=org_id)
    container.login("user@test.com", "123")

    @requires_same_organization(lambda: container, lambda: "other-org-id")
    def fn():
        return "ok"

    with pytest.raises(PermissionError):
        fn()


def test_check_plan_limit_bloqueia_free_apos_um_usuario():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    auth = c.auth()
    org_id = auth.create_organization("Acme")

    auth.register_user("user@test.com", "123", organization_id=org_id)
    c.login("user@test.com", "123")

    with pytest.raises(PermissionError):
        c.check_plan_limit("users")


def test_check_plan_limit_permite_com_plano_enterprise():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    auth = c.auth()
    org_id = auth.create_organization("Acme")
    auth.set_organization_plan(org_id, "enterprise")

    auth.register_user("user@test.com", "123", organization_id=org_id)
    c.login("user@test.com", "123")

    c.check_plan_limit("users")


def test_execute_with_limit_funciona_e_incrementa_uso():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    auth = c.auth()
    org_id = auth.create_organization("Acme")

    auth.register_user("user@test.com", "123", organization_id=org_id)
    c.login("user@test.com", "123")

    def fn():
        return "ok"

    assert c.execute_with_limit("requests_per_day", fn) == "ok"
    assert auth.get_usage_for_org(org_id) == 1


def test_execute_with_limit_bloqueia_apos_esgotar_cota():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    auth = c.auth()
    org_id = auth.create_organization("Acme")

    auth.register_user("user@test.com", "123", organization_id=org_id)
    c.login("user@test.com", "123")

    def fn():
        return "ok"

    for _ in range(100):
        c.execute_with_limit("requests_per_day", fn)

    with pytest.raises(PermissionError):
        c.execute_with_limit("requests_per_day", fn)


def test_upgrade_plan_owner_funciona():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    auth = c.auth()
    org_id = auth.create_organization("Acme")

    auth.register_user("owner@test.com", "123", organization_id=org_id, organization_role="owner")
    c.login("owner@test.com", "123")

    c.upgrade_plan("pro")

    assert auth.get_organization_plan(org_id) == "pro"


def test_upgrade_plan_nao_owner_bloqueia():
    c = PlatformContainer(bootstrap=PlatformBootstrap())
    auth = c.auth()
    org_id = auth.create_organization("Acme")

    auth.register_user(
        "member@test.com", "123", organization_id=org_id, organization_role="member"
    )
    c.login("member@test.com", "123")

    with pytest.raises(PermissionError):
        c.upgrade_plan("pro")

    assert auth.get_organization_plan(org_id) == "free"


def test_requires_limit_decorator_funciona():
    from app.platform.auth.platform_auth_decorators import requires_limit

    container = PlatformContainer(bootstrap=PlatformBootstrap())
    auth = container.auth()
    org_id = auth.create_organization("Acme")
    auth.register_user("user@test.com", "123", organization_id=org_id)
    container.login("user@test.com", "123")

    @requires_limit(lambda: container, "requests_per_day")
    def fn():
        return "ok"

    assert fn() == "ok"


def test_requires_limit_decorator_bloqueia():
    from app.platform.auth.platform_auth_decorators import requires_limit

    container = PlatformContainer(bootstrap=PlatformBootstrap())
    auth = container.auth()
    org_id = auth.create_organization("Acme")
    auth.register_user("user@test.com", "123", organization_id=org_id)
    container.login("user@test.com", "123")

    @requires_limit(lambda: container, "users")
    def fn():
        return "ok"

    with pytest.raises(PermissionError):
        fn()
