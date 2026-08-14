import inspect

from app.platform.bootstrap import platform_bootstrap
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_bootstrap_factory import build_default_platform_bootstrap
from app.platform.bootstrap.platform_service_catalog import PlatformServiceCatalog
from app.platform.health.platform_health_facade import PlatformHealthFacade

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
    "build_default_platform_lifecycle",
    "build_default_platform_events",
    "build_default_platform_capabilities",
    "build_default_platform_features",
]

_METHOD_NAMES = [
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
    "catalog",
]


def test_runtime_e_singleton():
    bootstrap = PlatformBootstrap()

    assert bootstrap.runtime() is bootstrap.runtime()


def test_operations_e_singleton():
    bootstrap = PlatformBootstrap()

    assert bootstrap.operations() is bootstrap.operations()


def test_command_bus_e_singleton():
    bootstrap = PlatformBootstrap()

    assert bootstrap.command_bus() is bootstrap.command_bus()


def test_query_bus_e_singleton():
    bootstrap = PlatformBootstrap()

    assert bootstrap.query_bus() is bootstrap.query_bus()


def test_application_e_singleton():
    bootstrap = PlatformBootstrap()

    assert bootstrap.application() is bootstrap.application()


def test_presentation_e_singleton():
    bootstrap = PlatformBootstrap()

    assert bootstrap.presentation() is bootstrap.presentation()


def test_platform_interface_e_singleton():
    bootstrap = PlatformBootstrap()

    assert bootstrap.platform_interface() is bootstrap.platform_interface()


def test_orchestrator_e_singleton():
    bootstrap = PlatformBootstrap()

    assert bootstrap.orchestrator() is bootstrap.orchestrator()


def test_health_e_singleton():
    bootstrap = PlatformBootstrap()

    assert bootstrap.health() is bootstrap.health()


def test_health_retorna_platform_health_facade():
    bootstrap = PlatformBootstrap()

    assert isinstance(bootstrap.health(), PlatformHealthFacade)


def test_registry_publica_health_sem_reconstruir(monkeypatch):
    calls = {"count": 0}
    original = platform_bootstrap.build_default_platform_health_facade

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(platform_bootstrap, "build_default_platform_health_facade", _spy)

    bootstrap = PlatformBootstrap()
    health_instance = bootstrap.health()
    registry = bootstrap.registry()

    assert calls["count"] == 1
    assert registry.find("health").instance is health_instance


def test_lifecycle_e_singleton():
    bootstrap = PlatformBootstrap()

    assert bootstrap.lifecycle() is bootstrap.lifecycle()


def test_lifecycle_retorna_platform_lifecycle():
    from app.platform.lifecycle.platform_lifecycle import PlatformLifecycle

    bootstrap = PlatformBootstrap()

    assert isinstance(bootstrap.lifecycle(), PlatformLifecycle)


def test_registry_publica_lifecycle_sem_reconstruir(monkeypatch):
    calls = {"count": 0}
    original = platform_bootstrap.build_default_platform_lifecycle

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(platform_bootstrap, "build_default_platform_lifecycle", _spy)

    bootstrap = PlatformBootstrap()
    lifecycle_instance = bootstrap.lifecycle()
    registry = bootstrap.registry()

    assert calls["count"] == 1
    descriptor = registry.find("lifecycle")
    assert descriptor is not None
    assert descriptor.name == "lifecycle"
    assert descriptor.instance is lifecycle_instance


def test_events_e_singleton():
    bootstrap = PlatformBootstrap()

    assert bootstrap.events() is bootstrap.events()


def test_events_retorna_platform_events():
    from app.platform.events.platform_events import PlatformEvents

    bootstrap = PlatformBootstrap()

    assert isinstance(bootstrap.events(), PlatformEvents)


def test_registry_publica_events_sem_reconstruir(monkeypatch):
    calls = {"count": 0}
    original = platform_bootstrap.build_default_platform_events

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(platform_bootstrap, "build_default_platform_events", _spy)

    bootstrap = PlatformBootstrap()
    events_instance = bootstrap.events()
    registry = bootstrap.registry()

    assert calls["count"] == 1
    descriptor = registry.find("events")
    assert descriptor is not None
    assert descriptor.name == "events"
    assert descriptor.instance is events_instance


def test_capabilities_e_singleton():
    bootstrap = PlatformBootstrap()

    assert bootstrap.capabilities() is bootstrap.capabilities()


def test_capabilities_retorna_platform_capabilities():
    from app.platform.capabilities.platform_capabilities import PlatformCapabilities

    bootstrap = PlatformBootstrap()

    assert isinstance(bootstrap.capabilities(), PlatformCapabilities)


def test_registry_publica_capabilities_sem_reconstruir(monkeypatch):
    calls = {"count": 0}
    original = platform_bootstrap.build_default_platform_capabilities

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(platform_bootstrap, "build_default_platform_capabilities", _spy)

    bootstrap = PlatformBootstrap()
    capabilities_instance = bootstrap.capabilities()
    registry = bootstrap.registry()

    assert calls["count"] == 1
    descriptor = registry.find("capabilities")
    assert descriptor is not None
    assert descriptor.name == "capabilities"
    assert descriptor.instance is capabilities_instance


def test_features_e_singleton():
    bootstrap = PlatformBootstrap()

    assert bootstrap.features() is bootstrap.features()


def test_features_retorna_platform_features():
    from app.platform.features.platform_features import PlatformFeatures

    bootstrap = PlatformBootstrap()

    assert isinstance(bootstrap.features(), PlatformFeatures)


def test_registry_publica_features_sem_reconstruir(monkeypatch):
    calls = {"count": 0}
    original = platform_bootstrap.build_default_platform_features

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(platform_bootstrap, "build_default_platform_features", _spy)

    bootstrap = PlatformBootstrap()
    features_instance = bootstrap.features()
    registry = bootstrap.registry()

    assert calls["count"] == 1
    descriptor = registry.find("features")
    assert descriptor is not None
    assert descriptor.name == "features"
    assert descriptor.instance is features_instance


def test_catalog_e_singleton():
    bootstrap = PlatformBootstrap()

    assert bootstrap.catalog() is bootstrap.catalog()


def test_catalog_retorna_platform_service_catalog():
    bootstrap = PlatformBootstrap()

    assert isinstance(bootstrap.catalog(), PlatformServiceCatalog)


def test_catalog_reutiliza_registry_existente(monkeypatch):
    calls = {"count": 0}
    original = PlatformBootstrap._build_registry

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(PlatformBootstrap, "_build_registry", _spy)

    bootstrap = PlatformBootstrap()
    bootstrap.registry()
    bootstrap.catalog()

    assert calls["count"] == 1


def test_catalog_nao_reconstroi_servicos(monkeypatch):
    calls = {"count": 0}
    original = platform_bootstrap.build_default_runtime_engine

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(platform_bootstrap, "build_default_runtime_engine", _spy)

    bootstrap = PlatformBootstrap()
    bootstrap.registry()
    bootstrap.catalog()

    assert calls["count"] == 1


def test_catalog_contem_os_mesmos_descritores_do_registry():
    bootstrap = PlatformBootstrap()
    registry = bootstrap.registry()
    catalog = bootstrap.catalog()

    assert catalog.services() == registry.list()


def test_catalog_utiliza_exclusivamente_a_factory_oficial():
    source = inspect.getsource(platform_bootstrap)

    assert "app.platform.bootstrap.platform_service_catalog_factory" in source
    assert "build_platform_service_catalog" in source


def test_build_catalog_nao_conhece_container_nem_kernel_facade():
    source = inspect.getsource(PlatformBootstrap._build_catalog)

    assert "build_platform_service_catalog" in source
    assert "PlatformServiceRegistry(" not in source
    assert "PlatformServiceResolver(" not in source
    assert "PlatformContainer" not in source
    assert "PlatformKernelFacade" not in source


def test_catalog_nao_esta_registrado_no_registry():
    bootstrap = PlatformBootstrap()

    registry = bootstrap.registry()

    assert registry.find("catalog") is None
    assert registry.exists("catalog") is False


def test_catalog_chamado_primeiro_nao_causa_recursao():
    bootstrap = PlatformBootstrap()

    catalog = bootstrap.catalog()

    assert isinstance(catalog, PlatformServiceCatalog)


def test_registry_chamado_primeiro_nao_causa_recursao():
    bootstrap = PlatformBootstrap()

    registry = bootstrap.registry()

    assert registry is not None


def test_build_registry_nao_referencia_catalog():
    source = inspect.getsource(PlatformBootstrap._build_registry)

    assert "catalog" not in source.lower()


def test_bootstraps_diferentes_possuem_instancias_diferentes():
    first = PlatformBootstrap()
    second = PlatformBootstrap()

    assert first.runtime() is not second.runtime()
    assert first.operations() is not second.operations()
    assert first.command_bus() is not second.command_bus()
    assert first.query_bus() is not second.query_bus()
    assert first.application() is not second.application()
    assert first.presentation() is not second.presentation()
    assert first.platform_interface() is not second.platform_interface()
    assert first.orchestrator() is not second.orchestrator()
    assert first.health() is not second.health()
    assert first.lifecycle() is not second.lifecycle()
    assert first.events() is not second.events()
    assert first.capabilities() is not second.capabilities()
    assert first.features() is not second.features()


def test_cada_factory_e_chamada_apenas_uma_vez(monkeypatch):
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
    for method_name in _METHOD_NAMES:
        method = getattr(bootstrap, method_name)
        method()
        method()
        method()

    assert all(count == 1 for count in call_counts.values())


def test_factory_retorna_platform_bootstrap():
    bootstrap = build_default_platform_bootstrap()

    assert isinstance(bootstrap, PlatformBootstrap)


def test_bootstrap_conhece_apenas_factories_oficiais():
    source = inspect.getsource(platform_bootstrap)

    for factory_name in _FACTORY_NAMES:
        assert factory_name in source


def test_bootstrap_nao_instancia_nenhuma_classe_concreta():
    source = inspect.getsource(platform_bootstrap)

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
        "PlatformHealthFacade(",
        "PlatformLifecycle(",
        "PlatformEvents(",
        "PlatformCapabilities(",
        "PlatformFeatures(",
        "PlatformServiceCatalog(",
    ]
    for pattern in forbidden_instantiations:
        assert pattern not in source


def test_nenhum_import_de_dominios_sem_factory_usada_pelo_bootstrap():
    source = inspect.getsource(platform_bootstrap)

    assert "app.crm" not in source
    assert "app.workflows" not in source
    assert "app.decision" not in source
    assert "app.automation" not in source
    assert "app.contracts" not in source
    assert "app.observability" not in source


def test_bootstrap_nao_importa_submodulos_internos_de_runtime_alem_da_factory():
    source = inspect.getsource(platform_bootstrap)

    assert "app.runtime.services.runtime_engine_factory" in source
    assert "app.runtime.engine" not in source
    assert "app.runtime.models" not in source
    assert "RuntimeEngine" not in source


def test_bootstrap_nao_importa_submodulos_internos_de_operations_alem_da_factory():
    source = inspect.getsource(platform_bootstrap)

    assert "app.operations.coordinator.operations_coordinator_factory" in source
    assert "OperationsCoordinator" not in source


def test_bootstrap_nao_importa_submodulos_internos_de_presentation_alem_da_factory():
    source = inspect.getsource(platform_bootstrap)

    assert "app.presentation.presentation_facade_factory" in source
    assert "PresentationFacade" not in source


def test_bootstrap_nao_importa_submodulos_internos_de_interface_alem_da_factory():
    source = inspect.getsource(platform_bootstrap)

    assert "app.interface.platform_interface_factory" in source
    assert "PlatformInterface" not in source


def test_health_utiliza_exclusivamente_a_factory_oficial():
    source = inspect.getsource(platform_bootstrap)

    assert "app.platform.health.platform_health_facade_factory" in source
    assert "build_default_platform_health_facade" in source


def test_bootstrap_nenhuma_referencia_a_componentes_concretos_de_health():
    source = inspect.getsource(platform_bootstrap)

    assert "HealthCoordinator" not in source
    assert "HealthMonitor" not in source
    assert "PlatformHealth" not in source
    assert "HealthReportService" not in source
    assert "HealthExecutor" not in source
    assert "HealthManager" not in source
    assert "HealthCheckRegistry" not in source
    assert "HealthCheck" not in source


def test_lifecycle_utiliza_exclusivamente_a_factory_oficial():
    source = inspect.getsource(platform_bootstrap)

    assert "app.platform.lifecycle.platform_lifecycle_factory" in source
    assert "build_default_platform_lifecycle" in source


def test_bootstrap_nenhuma_referencia_a_componentes_concretos_de_lifecycle():
    source = inspect.getsource(platform_bootstrap)

    assert "LifecycleExecutor" not in source
    assert "LifecycleManager" not in source
    assert "LifecycleStarter" not in source
    assert "LifecycleStopper" not in source
    assert "LifecycleParticipant" not in source
    assert "LifecycleParticipantRegistry" not in source


def test_events_utiliza_exclusivamente_a_factory_oficial():
    source = inspect.getsource(platform_bootstrap)

    assert "app.platform.events.platform_events_factory" in source
    assert "build_default_platform_events" in source


def test_bootstrap_nenhuma_referencia_a_componentes_concretos_de_events():
    source = inspect.getsource(platform_bootstrap)

    assert "PlatformEventExecutor" not in source
    assert "PlatformEventManager" not in source
    assert "EventRegistry" not in source
    assert "PlatformEvent" not in source


def test_capabilities_utiliza_exclusivamente_a_factory_oficial():
    source = inspect.getsource(platform_bootstrap)

    assert "app.platform.capabilities.platform_capabilities_factory" in source
    assert "build_default_platform_capabilities" in source


def test_bootstrap_nenhuma_referencia_a_componentes_concretos_de_capabilities():
    source = inspect.getsource(platform_bootstrap)

    assert "CapabilityExecutor" not in source
    assert "CapabilityManager" not in source
    assert "CapabilityRegistry" not in source
    assert "Capability" not in source


def test_features_utiliza_exclusivamente_a_factory_oficial():
    source = inspect.getsource(platform_bootstrap)

    assert "app.platform.features.platform_features_factory" in source
    assert "build_default_platform_features" in source


def test_bootstrap_nenhuma_referencia_a_componentes_concretos_de_features():
    source = inspect.getsource(platform_bootstrap)

    assert "FeatureExecutor" not in source
    assert "FeatureManager" not in source
    assert "FeatureRegistry" not in source
    assert "Feature" not in source


def test_bootstrap_factory_conhece_apenas_platform_bootstrap():
    from app.platform.bootstrap import platform_bootstrap_factory

    source = inspect.getsource(platform_bootstrap_factory)
    assert "app.runtime" not in source
    assert "app.operations" not in source
    assert "app.presentation" not in source
    assert "app.interface" not in source
    assert "app.crm" not in source
    assert "app.workflows" not in source
    assert "app.decision" not in source
    assert "app.automation" not in source
    assert "app.contracts" not in source
    assert "app.observability" not in source
