from typing import Any

from app.platform.exceptions.platform_exceptions import ModuleNotRegisteredError
from app.platform.models.enums import ModuleType
from app.platform.models.platform_context import PlatformContext
from app.platform.models.platform_module import PlatformModule
from app.platform.registry.module_descriptor import ModuleDescriptor
from app.platform.registry.module_registry import ModuleRegistry
from app.platform.repositories.module_repository import ModuleRepository


class PlatformKernel:
    """The platform's single internal access point for "which modules exist and
    are they enabled". It implements no business rules, knows nothing about AI,
    CRM, Mission, or Prospect, and never imports WorkflowEngine, RuntimeEngine,
    CRMEngine, or anything AI-related — it only ever holds ModuleDescriptors.
    CLI, API, Workers, Scheduler, and the application's bootstrap will all resolve
    "is this module here, and is it enabled" through this one object.
    """

    def __init__(
        self,
        registry: ModuleRegistry,
        repository: ModuleRepository,
        *,
        context: PlatformContext,
        kernel_version: str = "1.0.0",
    ) -> None:
        self.registry = registry
        self.repository = repository
        self.context = context
        self.kernel_version = kernel_version

    def register_module(
        self, module_type: ModuleType, descriptor: ModuleDescriptor
    ) -> PlatformModule:
        module = PlatformModule(module_type=module_type, descriptor=descriptor)
        self.registry.register(module)
        self.repository.save_module(module)
        return module

    def get_module(self, module_type: ModuleType) -> PlatformModule:
        return self.registry.get(module_type)

    def list_modules(self) -> list[PlatformModule]:
        return self.registry.list()

    def is_registered(self, module_type: ModuleType) -> bool:
        try:
            self.registry.get(module_type)
            return True
        except ModuleNotRegisteredError:
            return False

    def health(self) -> dict[str, Any]:
        modules = self.registry.list()
        enabled = [m for m in modules if m.descriptor.enabled]
        disabled = [m for m in modules if not m.descriptor.enabled]
        return {
            "registered_modules": len(modules),
            "enabled_modules": len(enabled),
            "disabled_modules": len(disabled),
            "kernel_version": self.kernel_version,
            "platform_started_at": self.context.started_at,
        }

    def version(self) -> str:
        return self.kernel_version
