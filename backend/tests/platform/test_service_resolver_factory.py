import inspect

from app.platform.bootstrap import platform_bootstrap
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_service_descriptor import PlatformServiceDescriptor
from app.platform.bootstrap.platform_service_registry import PlatformServiceRegistry
from app.platform.bootstrap.platform_service_resolver import PlatformServiceResolver
from app.platform.bootstrap.platform_service_resolver_factory import (
    build_default_platform_service_resolver,
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
]

_FACTORY_NAMES = [
    "build_default_runtime_engine",
    "build_default_operations_coordinator",
    "build_default_command_bus_service",
    "build_default_query_bus_service",
    "build_default_public_use_case_service",
    "build_default_presentation_facade",
    "build_default_platform_interface",
    "build_default_platform_execution_orchestrator",
]


def test_factory_retorna_platform_service_resolver():
    registry = PlatformServiceRegistry()

    resolver = build_default_platform_service_resolver(registry=registry)

    assert isinstance(resolver, PlatformServiceResolver)


def test_registry_preservado():
    registry = PlatformServiceRegistry().register(
        PlatformServiceDescriptor(name="runtime", instance=object())
    )

    resolver = build_default_platform_service_resolver(registry=registry)

    assert resolver.registry is registry


def test_resolver_funciona_normalmente():
    instance = object()
    registry = PlatformServiceRegistry().register(
        PlatformServiceDescriptor(name="runtime", instance=instance)
    )

    resolver = build_default_platform_service_resolver(registry=registry)

    assert resolver.resolve("runtime") is instance
    assert resolver.exists("runtime") is True
    assert resolver.exists("does_not_exist") is False
    assert resolver.list() == registry.list()


def test_bootstrap_utiliza_exclusivamente_a_factory():
    source = inspect.getsource(platform_bootstrap)

    assert "build_default_platform_service_resolver" in source


def test_bootstrap_nao_instancia_platform_service_resolver_diretamente():
    source = inspect.getsource(platform_bootstrap)

    assert "PlatformServiceResolver(" not in source


def test_nenhuma_factory_chamada_duas_vezes(monkeypatch):
    call_counts = {name: 0 for name in _FACTORY_NAMES}

    def _install_spy(factory_name: str) -> None:
        original = getattr(platform_bootstrap, factory_name)

        def _spy(*args, **kwargs):
            call_counts[factory_name] += 1
            return original(*args, **kwargs)

        monkeypatch.setattr(platform_bootstrap, factory_name, _spy)

    for factory_name in _FACTORY_NAMES:
        _install_spy(factory_name)

    bootstrap = PlatformBootstrap()
    bootstrap.resolver()
    bootstrap.resolver()
    bootstrap.registry()
    for service_name in _SERVICE_NAMES:
        getattr(bootstrap, service_name)()

    assert all(count == 1 for count in call_counts.values())


def test_resolver_singleton_preservado():
    bootstrap = PlatformBootstrap()

    assert bootstrap.resolver() is bootstrap.resolver()


def test_registry_singleton_preservado():
    bootstrap = PlatformBootstrap()

    assert bootstrap.registry() is bootstrap.registry()


def test_identidade_preservada_entre_resolver_e_registry():
    bootstrap = PlatformBootstrap()

    resolver = bootstrap.resolver()

    assert resolver.registry is bootstrap.registry()
    for service_name in _SERVICE_NAMES:
        direct_instance = getattr(bootstrap, service_name)()
        assert resolver.resolve(service_name) is direct_instance
