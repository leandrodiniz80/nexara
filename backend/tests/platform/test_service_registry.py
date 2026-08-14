import inspect

import pytest
from pydantic import ValidationError

from app.platform.bootstrap import platform_bootstrap, platform_service_registry
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_service_descriptor import PlatformServiceDescriptor
from app.platform.bootstrap.platform_service_registry import PlatformServiceRegistry

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

_FACTORY_NAMES = [
    "build_default_runtime_engine",
    "build_default_operations_coordinator",
    "build_default_command_bus_service",
    "build_default_query_bus_service",
    "build_default_public_use_case_service",
    "build_default_presentation_facade",
    "build_default_platform_interface",
    "build_default_platform_execution_orchestrator",
    "build_default_platform_health_facade",
]


# --- PlatformServiceDescriptor -------------------------------------------------


def test_descriptor_preserva_name_e_instance():
    instance = object()

    descriptor = PlatformServiceDescriptor(name="runtime", instance=instance)

    assert descriptor.name == "runtime"
    assert descriptor.instance is instance


def test_descriptor_imutabilidade_rejects_attribute_assignment():
    descriptor = PlatformServiceDescriptor(name="runtime", instance=object())

    with pytest.raises(ValidationError):
        descriptor.name = "altered"


# --- PlatformServiceRegistry (standalone) --------------------------------------


def test_registro_adds_the_given_descriptor():
    descriptor = PlatformServiceDescriptor(name="alpha", instance=object())
    registry = PlatformServiceRegistry()

    updated = registry.register(descriptor)

    assert updated.list() == [descriptor]
    assert registry.list() == []


def test_register_many_adds_every_given_descriptor_in_order():
    descriptor_a = PlatformServiceDescriptor(name="alpha", instance=object())
    descriptor_b = PlatformServiceDescriptor(name="beta", instance=object())
    registry = PlatformServiceRegistry()

    updated = registry.register_many([descriptor_a, descriptor_b])

    assert updated.list() == [descriptor_a, descriptor_b]


def test_find_existente_returns_the_matching_descriptor():
    descriptor = PlatformServiceDescriptor(name="alpha", instance=object())
    registry = PlatformServiceRegistry().register(descriptor)

    assert registry.find("alpha") is descriptor


def test_find_inexistente_returns_none():
    registry = PlatformServiceRegistry().register(
        PlatformServiceDescriptor(name="alpha", instance=object())
    )

    assert registry.find("does_not_exist") is None


def test_exists_true_and_false():
    registry = PlatformServiceRegistry().register(
        PlatformServiceDescriptor(name="alpha", instance=object())
    )

    assert registry.exists("alpha") is True
    assert registry.exists("does_not_exist") is False


def test_imutabilidade_rejects_attribute_assignment():
    registry = PlatformServiceRegistry()

    with pytest.raises(ValidationError):
        registry.descriptors = ()


def test_registry_usa_apenas_registry_t():
    source = inspect.getsource(platform_service_registry)

    assert "Registry[PlatformServiceDescriptor]" in source
    assert "from app.shared.registry.registry import Registry" in source
    assert "for descriptor in" not in source
    assert "for item in" not in source


def test_registry_nao_instancia_nenhuma_classe_concreta_de_servico():
    source = inspect.getsource(platform_service_registry)

    forbidden_instantiations = [
        "RuntimeEngine(",
        "OperationsCoordinator(",
        "CommandBus(",
        "QueryBus(",
        "PresentationFacade(",
        "PlatformInterface(",
        "PlatformExecutionOrchestrator(",
        "PlatformHealthFacade(",
    ]
    for pattern in forbidden_instantiations:
        assert pattern not in source


def test_registry_conhece_exclusivamente_platform_service_descriptor():
    source = inspect.getsource(platform_service_registry)

    assert "PlatformServiceDescriptor" in source
    assert "PlatformHealthFacade" not in source
    assert "RuntimeEngine" not in source
    assert "OperationsCoordinator" not in source
    assert "app.platform.health" not in source
    assert "app.runtime" not in source
    assert "app.operations" not in source


# --- PlatformBootstrap.registry() integration ----------------------------------


def test_registry_e_singleton():
    bootstrap = PlatformBootstrap()

    assert bootstrap.registry() is bootstrap.registry()


def test_registry_contem_exatamente_nove_servicos():
    bootstrap = PlatformBootstrap()

    assert len(bootstrap.registry().list()) == 9


@pytest.mark.parametrize("service_name", _SERVICE_NAMES)
def test_servico_preserva_identidade(service_name: str):
    bootstrap = PlatformBootstrap()
    method = getattr(bootstrap, service_name)

    direct_instance = method()
    descriptor = bootstrap.registry().find(service_name)

    assert descriptor is not None
    assert descriptor.instance is direct_instance


def test_registry_find_de_todos_os_nomes_registrados():
    bootstrap = PlatformBootstrap()
    registry = bootstrap.registry()

    for service_name in _SERVICE_NAMES:
        assert registry.find(service_name) is not None


def test_registry_exists_de_todos_os_nomes_registrados():
    bootstrap = PlatformBootstrap()
    registry = bootstrap.registry()

    for service_name in _SERVICE_NAMES:
        assert registry.exists(service_name) is True
    assert registry.exists("does_not_exist") is False


def test_registry_list_returns_all_nine_descriptors():
    bootstrap = PlatformBootstrap()

    names = {descriptor.name for descriptor in bootstrap.registry().list()}

    assert names == set(_SERVICE_NAMES)


def test_health_descriptor_name_e_health():
    bootstrap = PlatformBootstrap()

    descriptor = bootstrap.registry().find("health")

    assert descriptor is not None
    assert descriptor.name == "health"


def test_health_descriptor_instance_is_bootstrap_health():
    bootstrap = PlatformBootstrap()

    descriptor = bootstrap.registry().find("health")

    assert descriptor.instance is bootstrap.health()


def test_registry_nao_reconstroi_servicos_ja_cacheados():
    bootstrap = PlatformBootstrap()
    direct_instances = {name: getattr(bootstrap, name)() for name in _SERVICE_NAMES}

    registry = bootstrap.registry()

    for name in _SERVICE_NAMES:
        assert registry.find(name).instance is direct_instances[name]


def test_nenhuma_factory_chamada_novamente_ao_construir_registry(monkeypatch):
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
    for service_name in _SERVICE_NAMES:
        getattr(bootstrap, service_name)()

    bootstrap.registry()
    bootstrap.registry()

    assert all(count == 1 for count in call_counts.values())


def test_registry_via_bootstrap_novo_nao_reutiliza_instancias_de_outro():
    first = PlatformBootstrap()
    second = PlatformBootstrap()

    first_runtime = first.registry().find("runtime").instance
    second_runtime = second.registry().find("runtime").instance

    assert first_runtime is not second_runtime
