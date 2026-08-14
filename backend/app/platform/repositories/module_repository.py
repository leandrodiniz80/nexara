from app.platform.models.enums import ModuleType
from app.platform.models.platform_module import PlatformModule


class ModuleRepository:
    """In-memory, durable record of every registered PlatformModule — no
    database, no migration was requested for this module. Distinct from
    ModuleRegistry: the registry is the live "what's active right now" lookup,
    this is the persisted store PlatformKernel writes through to on every
    register_module() call.
    """

    def __init__(self) -> None:
        self._modules: dict[ModuleType, PlatformModule] = {}

    def save_module(self, module: PlatformModule) -> PlatformModule:
        self._modules[module.module_type] = module
        return module

    def get_module(self, module_type: ModuleType) -> PlatformModule | None:
        return self._modules.get(module_type)

    def list_modules(self) -> list[PlatformModule]:
        return list(self._modules.values())
