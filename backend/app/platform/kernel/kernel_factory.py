from app.platform.kernel.kernel_builder import KernelBuilder
from app.platform.kernel.platform_kernel import PlatformKernel
from app.platform.models.enums import ModuleType
from app.platform.registry.module_registry import ModuleRegistry
from app.platform.repositories.module_repository import ModuleRepository

_DEFAULT_MODULES: dict[ModuleType, dict[str, str]] = {
    ModuleType.MISSION: {
        "name": "Mission",
        "version": "1.0.0",
        "description": "Prospecting mission lifecycle.",
    },
    ModuleType.RESEARCH: {
        "name": "Research",
        "version": "1.0.0",
        "description": "Company discovery and enrichment.",
    },
    ModuleType.AI: {
        "name": "AI",
        "version": "1.0.0",
        "description": "Copy generation and orchestration.",
    },
    ModuleType.OUTREACH: {
        "name": "Outreach",
        "version": "1.0.0",
        "description": "Message delivery and outreach assets.",
    },
    ModuleType.WORKFLOW: {
        "name": "Workflow",
        "version": "1.0.0",
        "description": "Task sequencing engine.",
    },
    ModuleType.AUTOMATION: {
        "name": "Automation",
        "version": "1.0.0",
        "description": "Trigger-driven Workflow execution.",
    },
    ModuleType.RUNTIME: {
        "name": "Runtime",
        "version": "1.0.0",
        "description": "Single execution entrypoint for the platform.",
    },
    ModuleType.CRM: {
        "name": "CRM",
        "version": "1.0.0",
        "description": "Commercial relationship modeling.",
    },
    ModuleType.OBSERVABILITY: {
        "name": "Observability",
        "version": "1.0.0",
        "description": "Platform monitoring and tracing.",
    },
    ModuleType.API: {
        "name": "API",
        "version": "1.0.0",
        "description": "HTTP interface for the platform.",
    },
    ModuleType.APPLICATION: {
        "name": "Application",
        "version": "1.0.0",
        "description": "Application services layer.",
    },
}


def build_default_platform_kernel(
    *,
    registry: ModuleRegistry | None = None,
    repository: ModuleRepository | None = None,
    environment: str = "development",
    application_version: str = "0.1.0",
) -> PlatformKernel:
    """Composition root for this module — registers a static ModuleDescriptor for
    every known ModuleType. Purely metadata: no Engine, Agent, or Provider from
    any of those modules is imported or constructed here, only plain strings
    describing them.
    """
    kernel = PlatformKernel(
        registry=registry or ModuleRegistry(),
        repository=repository or ModuleRepository(),
        context=KernelBuilder.build_context(
            environment=environment, application_version=application_version
        ),
    )
    for module_type, info in _DEFAULT_MODULES.items():
        kernel.register_module(module_type, KernelBuilder.build_descriptor(**info))
    return kernel
