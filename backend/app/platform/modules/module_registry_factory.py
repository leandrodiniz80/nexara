from app.platform.modules.default_platform_module import DefaultPlatformModule
from app.platform.modules.module_registry import ModuleRegistry


def build_default_module_registry() -> ModuleRegistry:
    """Composition root for this registry. Registers exactly the platform's
    own built-in module, DefaultPlatformModule.
    """
    return ModuleRegistry().register(DefaultPlatformModule())
