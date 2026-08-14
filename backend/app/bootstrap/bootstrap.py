from app.bootstrap.container import DependencyContainer
from app.bootstrap.module_loader import BootstrapModule, ModuleLoader
from app.bootstrap.service_locator import ServiceLocator
from app.config.configuration import load_platform_settings
from app.config.settings import PlatformSettings

_MODULE_ENABLED_FLAGS: dict[BootstrapModule, str] = {
    BootstrapModule.CRM: "crm_enabled",
    BootstrapModule.RUNTIME: "runtime_enabled",
    BootstrapModule.WORKFLOW: "workflow_enabled",
    BootstrapModule.AUTOMATION: "automation_enabled",
    BootstrapModule.OBSERVABILITY: "observability_enabled",
}


class Bootstrap:
    """The platform's official Composition Root. It depends exclusively on
    PlatformSettings (app.config) for every value that decides what to build
    and how — it holds no hardcoded default of its own. When no settings are
    given, it loads them the same way any future caller would:
    `load_platform_settings()`, which already merges the platform's built-in
    defaults with real environment variables and validates the result before
    this class ever sees it. "Nothing configured" therefore means exactly
    what it always meant: the platform's own defaults — Bootstrap() with no
    arguments still builds every module exactly as it did before this class
    depended on PlatformSettings.

    It calls every enabled module's existing `build_default_*` Factory
    (through ModuleLoader — never constructing a module by hand), registers
    each result into a DependencyContainer keyed by its concrete type, and
    hands the result out as a read-only ServiceLocator. It implements no
    business rule and integrates no module with another — it only builds and
    holds.
    """

    def __init__(
        self,
        settings: PlatformSettings | None = None,
        *,
        module_loader: ModuleLoader | None = None,
    ) -> None:
        self.settings = settings or load_platform_settings()
        self.module_loader = module_loader or ModuleLoader()
        self.container = DependencyContainer()
        self._initialized = False

    def initialize(self) -> ServiceLocator:
        for module in self._enabled_modules():
            instance = self.module_loader.load(module)
            self.container.register(instance)
        self._initialized = True
        return self.locator()

    def _enabled_modules(self) -> list[BootstrapModule]:
        requested = [BootstrapModule(name.value) for name in self.settings.enabled_modules]
        return [module for module in requested if self._is_enabled(module)]

    def _is_enabled(self, module: BootstrapModule) -> bool:
        flag_name = _MODULE_ENABLED_FLAGS.get(module)
        if flag_name is None:
            return True
        return getattr(self.settings, flag_name)

    def locator(self) -> ServiceLocator:
        return ServiceLocator(self.container)

    def shutdown(self) -> None:
        self.container = DependencyContainer()
        self._initialized = False

    def is_initialized(self) -> bool:
        return self._initialized
