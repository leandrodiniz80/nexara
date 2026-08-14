import inspect

import pytest
from pydantic import ValidationError

from app.platform.bootstrap import platform_service_resolver
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_service_descriptor import PlatformServiceDescriptor
from app.platform.bootstrap.platform_service_registry import PlatformServiceRegistry
from app.platform.bootstrap.platform_service_resolver import PlatformServiceResolver

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
]


def _registry(*names: str) -> PlatformServiceRegistry:
    return PlatformServiceRegistry().register_many(
        [PlatformServiceDescriptor(name=name, instance=object()) for name in names]
    )


# --- PlatformServiceResolver (standalone) --------------------------------------


def test_resolve_existente_returns_the_published_instance():
    instance = object()
    registry = PlatformServiceRegistry().register(
        PlatformServiceDescriptor(name="runtime", instance=instance)
    )
    resolver = PlatformServiceResolver(registry=registry)

    assert resolver.resolve("runtime") is instance


def test_resolve_inexistente_levanta_key_error():
    resolver = PlatformServiceResolver(registry=PlatformServiceRegistry())

    with pytest.raises(KeyError):
        resolver.resolve("does_not_exist")


def test_resolve_nunca_retorna_none():
    registry = _registry("runtime")
    resolver = PlatformServiceResolver(registry=registry)

    result = resolver.resolve("runtime")

    assert result is not None


def test_exists_delega_diretamente_ao_registry():
    resolver = PlatformServiceResolver(registry=_registry("runtime"))

    assert resolver.exists("runtime") is True
    assert resolver.exists("does_not_exist") is False


def test_list_delega_diretamente_ao_registry():
    registry = _registry("runtime", "operations")
    resolver = PlatformServiceResolver(registry=registry)

    assert resolver.list() == registry.list()


def test_imutabilidade_rejects_attribute_assignment():
    resolver = PlatformServiceResolver(registry=_registry("runtime"))

    with pytest.raises(ValidationError):
        resolver.registry = PlatformServiceRegistry()


def test_injecao_uses_exactly_the_registry_provided():
    registry = _registry("runtime")

    resolver = PlatformServiceResolver(registry=registry)

    assert resolver.registry is registry


def test_resolver_conhece_apenas_platform_service_registry():
    source = inspect.getsource(platform_service_resolver)

    assert "PlatformServiceRegistry" in source
    assert "PlatformServiceDescriptor" not in source


def test_resolver_nenhuma_factory():
    source = inspect.getsource(platform_service_resolver)

    assert "factory" not in source.lower()
    assert "build_default" not in source


def test_resolver_nenhum_engine():
    source = inspect.getsource(platform_service_resolver)

    assert "Engine" not in source
    assert "app.runtime" not in source
    assert "app.operations" not in source


def test_resolver_nenhum_service_concreto():
    source = inspect.getsource(platform_service_resolver)

    assert "CommandBusService" not in source
    assert "QueryBusService" not in source
    assert "PublicUseCaseService" not in source
    assert "PresentationFacade" not in source
    assert "PlatformInterface" not in source
    assert "PlatformExecutionOrchestrator" not in source


def test_resolver_nenhuma_instanciacao_direta():
    source = inspect.getsource(platform_service_resolver)

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


# --- PlatformBootstrap.resolver() integration ----------------------------------


def test_resolver_e_singleton():
    bootstrap = PlatformBootstrap()

    assert bootstrap.resolver() is bootstrap.resolver()


@pytest.mark.parametrize("service_name", _SERVICE_NAMES)
def test_resolve_via_bootstrap_preserva_identidade(service_name: str):
    bootstrap = PlatformBootstrap()
    direct_instance = getattr(bootstrap, service_name)()

    resolved = bootstrap.resolver().resolve(service_name)

    assert resolved is direct_instance


def test_resolve_inexistente_via_bootstrap_levanta_key_error():
    bootstrap = PlatformBootstrap()

    with pytest.raises(KeyError):
        bootstrap.resolver().resolve("does_not_exist")


def test_exists_via_bootstrap():
    bootstrap = PlatformBootstrap()
    resolver = bootstrap.resolver()

    for service_name in _SERVICE_NAMES:
        assert resolver.exists(service_name) is True
    assert resolver.exists("does_not_exist") is False


def test_list_via_bootstrap_returns_nine_descriptors():
    bootstrap = PlatformBootstrap()

    assert len(bootstrap.resolver().list()) == 9


def test_resolve_health_via_bootstrap_retorna_exatamente_bootstrap_health():
    bootstrap = PlatformBootstrap()

    resolved = bootstrap.resolver().resolve("health")

    assert resolved is bootstrap.health()


def test_exists_health_via_bootstrap():
    bootstrap = PlatformBootstrap()

    assert bootstrap.resolver().exists("health") is True


def test_list_via_bootstrap_contem_health():
    bootstrap = PlatformBootstrap()

    names = {descriptor.name for descriptor in bootstrap.resolver().list()}

    assert "health" in names


def test_registry_chamado_exatamente_uma_vez(monkeypatch):
    original_registry = PlatformBootstrap.registry
    calls = {"count": 0}

    def _spy(self):
        calls["count"] += 1
        return original_registry(self)

    monkeypatch.setattr(PlatformBootstrap, "registry", _spy)

    bootstrap = PlatformBootstrap()
    bootstrap.resolver()
    bootstrap.resolver()
    bootstrap.resolver()

    assert calls["count"] == 1
