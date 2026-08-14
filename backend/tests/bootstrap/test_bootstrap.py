from app.bootstrap.bootstrap import Bootstrap
from app.bootstrap.module_loader import BootstrapModule, ModuleLoader
from app.config.configuration import load_platform_settings
from app.config.constants import ModuleName
from app.config.environment import EnvironmentVariablesProvider
from app.config.loader import ConfigurationLoader
from app.config.providers import DefaultConfigurationProvider
from app.config.settings import PlatformSettings


class _ServiceA:
    pass


class _ServiceB:
    pass


class _ServiceC:
    pass


class _FakeModuleLoader:
    """Satisfies exactly the shape Bootstrap relies on
    (`load(module) -> object`) — lets these tests exercise Bootstrap's own
    coordination logic without constructing all fourteen real platform
    engines every time. Only supports CRM/RUNTIME/AI, so every test using it
    must restrict PlatformSettings.enabled_modules to a subset of those three.
    AI is included specifically to exercise a module with no
    PlatformSettings.<name>_enabled flag of its own.
    """

    _BUILDERS = {
        BootstrapModule.CRM: _ServiceA,
        BootstrapModule.RUNTIME: _ServiceB,
        BootstrapModule.AI: _ServiceC,
    }

    def __init__(self) -> None:
        self.load_calls: list[BootstrapModule] = []

    def load(self, module: BootstrapModule) -> object:
        self.load_calls.append(module)
        return self._BUILDERS[module]()


def _settings(**overrides) -> PlatformSettings:
    return PlatformSettings(**overrides)


def test_initialize_builds_exactly_the_settings_enabled_modules():
    loader = _FakeModuleLoader()
    settings = _settings(enabled_modules=["crm", "runtime"])
    bootstrap = Bootstrap(settings, module_loader=loader)

    locator = bootstrap.initialize()

    assert set(loader.load_calls) == {BootstrapModule.CRM, BootstrapModule.RUNTIME}
    assert locator.has(_ServiceA) is True
    assert locator.has(_ServiceB) is True


def test_initialize_returns_a_service_locator_with_the_right_instances():
    loader = _FakeModuleLoader()
    settings = _settings(enabled_modules=["crm", "runtime"])
    bootstrap = Bootstrap(settings, module_loader=loader)

    locator = bootstrap.initialize()

    assert isinstance(locator.get(_ServiceA), _ServiceA)
    assert isinstance(locator.get(_ServiceB), _ServiceB)


def test_initialize_only_builds_the_configured_enabled_modules():
    loader = _FakeModuleLoader()
    settings = _settings(enabled_modules=["crm"])
    bootstrap = Bootstrap(settings, module_loader=loader)

    locator = bootstrap.initialize()

    assert loader.load_calls == [BootstrapModule.CRM]
    assert locator.has(_ServiceA) is True
    assert locator.has(_ServiceB) is False


def test_a_module_specific_disabled_flag_excludes_it_even_if_in_enabled_modules():
    """CRM/RUNTIME/WORKFLOW/AUTOMATION/OBSERVABILITY each have their own
    PlatformSettings.<name>_enabled flag — Bootstrap must honor it even when
    the module is still listed in enabled_modules."""
    loader = _FakeModuleLoader()
    settings = _settings(enabled_modules=["crm", "runtime"], crm_enabled=False)
    bootstrap = Bootstrap(settings, module_loader=loader)

    locator = bootstrap.initialize()

    assert loader.load_calls == [BootstrapModule.RUNTIME]
    assert locator.has(_ServiceA) is False
    assert locator.has(_ServiceB) is True


def test_a_module_without_its_own_enabled_flag_is_only_gated_by_enabled_modules():
    """AI/RESEARCH/... have no PlatformSettings.<name>_enabled field at all —
    being listed in enabled_modules is enough, regardless of any other
    module's disabled flag."""
    loader = _FakeModuleLoader()
    settings = _settings(enabled_modules=["ai"], runtime_enabled=False, crm_enabled=False)
    bootstrap = Bootstrap(settings, module_loader=loader)

    locator = bootstrap.initialize()

    assert loader.load_calls == [BootstrapModule.AI]
    assert locator.has(_ServiceC) is True


def test_a_module_without_its_own_enabled_flag_cannot_be_disabled_via_a_flag():
    """There is no PlatformSettings.ai_enabled field — AI can only be turned
    off by removing it from enabled_modules, never via a flag."""
    loader = _FakeModuleLoader()
    settings = _settings(enabled_modules=["ai", "crm"])
    bootstrap = Bootstrap(settings, module_loader=loader)

    bootstrap.initialize()

    assert set(loader.load_calls) == {BootstrapModule.AI, BootstrapModule.CRM}


def test_is_initialized_reflects_lifecycle_state():
    bootstrap = Bootstrap(_settings(enabled_modules=["crm"]), module_loader=_FakeModuleLoader())

    assert bootstrap.is_initialized() is False

    bootstrap.initialize()

    assert bootstrap.is_initialized() is True


def test_shutdown_clears_the_container_and_resets_initialized_state():
    loader = _FakeModuleLoader()
    bootstrap = Bootstrap(_settings(enabled_modules=["crm"]), module_loader=loader)
    bootstrap.initialize()

    bootstrap.shutdown()

    assert bootstrap.is_initialized() is False
    assert bootstrap.locator().has(_ServiceA) is False


def test_shutdown_before_any_initialize_does_not_raise():
    bootstrap = Bootstrap(_settings(enabled_modules=["crm"]), module_loader=_FakeModuleLoader())

    bootstrap.shutdown()

    assert bootstrap.is_initialized() is False


def test_locator_reflects_the_containers_current_state_even_before_initialize():
    bootstrap = Bootstrap(_settings(enabled_modules=["crm"]), module_loader=_FakeModuleLoader())

    assert bootstrap.locator().list_types() == []


def test_bootstrap_with_no_arguments_loads_platform_settings():
    """Bootstrap() with nothing given must load its settings from
    load_platform_settings() — the single official source — never from a
    value hardcoded inside Bootstrap itself."""
    bootstrap = Bootstrap()

    assert isinstance(bootstrap.settings, PlatformSettings)
    assert set(bootstrap.settings.enabled_modules) == set(ModuleName)


def test_environment_variables_override_which_modules_get_built():
    """Proves Bootstrap genuinely reads from PlatformSettings — not a second,
    hardcoded copy of "which modules to build". The real default enables all
    14 modules; a real ELEVEL_ENABLED_MODULES env var restricts that down to
    just the two the fake loader supports.
    """
    loader = _FakeModuleLoader()
    config_loader = ConfigurationLoader(
        providers=[
            DefaultConfigurationProvider(),
            EnvironmentVariablesProvider(environ={"ELEVEL_ENABLED_MODULES": "crm,runtime"}),
        ]
    )
    settings = load_platform_settings(config_loader)
    bootstrap = Bootstrap(settings, module_loader=loader)

    bootstrap.initialize()

    assert set(loader.load_calls) == {BootstrapModule.CRM, BootstrapModule.RUNTIME}


def test_environment_variables_can_disable_a_module_specific_flag():
    loader = _FakeModuleLoader()
    config_loader = ConfigurationLoader(
        providers=[
            DefaultConfigurationProvider(),
            EnvironmentVariablesProvider(
                environ={"ELEVEL_ENABLED_MODULES": "crm,runtime", "ELEVEL_RUNTIME_ENABLED": "false"}
            ),
        ]
    )
    settings = load_platform_settings(config_loader)
    bootstrap = Bootstrap(settings, module_loader=loader)

    bootstrap.initialize()

    assert loader.load_calls == [BootstrapModule.CRM]


def test_bootstrap_completo_with_the_real_module_loader_registers_every_real_module():
    """End-to-end: uses the real ModuleLoader (and, underneath it, every real
    module's own build_default_*() Factory) with the real, fully-defaulted
    PlatformSettings (all 14 modules enabled) — proving Bootstrap() with no
    arguments still behaves exactly as it did before this sprint. Only the
    Providers/Agents/Rules beneath those engines are the same mocks/defaults
    every other end-to-end test in this codebase relies on.
    """
    from app.ai.orchestrator.ai_orchestrator import AIOrchestrator
    from app.application.tasks.registry.task_registry import TaskRegistry
    from app.automation.engine.automation_engine import AutomationEngine
    from app.business_rules.engine.rules_engine import RulesEngine
    from app.crm.engine.crm_engine import CRMEngine
    from app.decision.engine.decision_engine import DecisionEngine
    from app.jobs.engine.job_engine import JobEngine
    from app.observability.engine.observability_engine import ObservabilityEngine
    from app.outreach.engine.outreach_engine import OutreachEngine
    from app.platform.kernel.platform_kernel import PlatformKernel
    from app.research.engine.research_engine import ResearchEngine
    from app.runtime.engine.runtime_engine import RuntimeEngine
    from app.sales_intelligence.engine.sales_intelligence_engine import SalesIntelligenceEngine
    from app.workflows.engine.workflow_engine import WorkflowEngine

    bootstrap = Bootstrap(module_loader=ModuleLoader())

    locator = bootstrap.initialize()

    expected_types = {
        AIOrchestrator,
        ResearchEngine,
        OutreachEngine,
        TaskRegistry,
        WorkflowEngine,
        AutomationEngine,
        RuntimeEngine,
        CRMEngine,
        DecisionEngine,
        RulesEngine,
        ObservabilityEngine,
        PlatformKernel,
        JobEngine,
        SalesIntelligenceEngine,
    }
    assert set(locator.list_types()) == expected_types
    for service_type in expected_types:
        assert isinstance(locator.get(service_type), service_type)
