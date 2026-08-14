from app.platform.exceptions.platform_exceptions import ModuleNotRegisteredError
from app.platform.models.enums import ModuleType
from app.platform.models.platform_module import PlatformModule


class ModuleRegistry:
    """Holds the currently registered PlatformModule for each ModuleType — one per
    type, the most recently registered one wins. This is the live lookup
    PlatformKernel talks to directly for get_module()/list_modules()/health();
    ModuleRepository (a separate store) is where every registration is persisted.
    """

    def __init__(self) -> None:
        self._modules: dict[ModuleType, PlatformModule] = {}

    def register(self, module: PlatformModule) -> PlatformModule:
        self._modules[module.module_type] = module
        return module

    def get(self, module_type: ModuleType) -> PlatformModule:
        module = self._modules.get(module_type)
        if module is None:
            raise ModuleNotRegisteredError(module_type)
        return module

    def list(self) -> list[PlatformModule]:
        return list(self._modules.values())

    def remove(self, module_type: ModuleType) -> None:
        self._modules.pop(module_type, None)
