from app.platform.models.platform_context import PlatformContext
from app.platform.registry.module_descriptor import ModuleDescriptor


class KernelBuilder:
    """Constructs ModuleDescriptors and PlatformContexts — the only place this
    construction logic lives, the same role PipelineBuilder/WorkflowBuilder play
    for their own modules."""

    @staticmethod
    def build_descriptor(
        *,
        name: str,
        version: str,
        enabled: bool = True,
        status: str = "stable",
        description: str = "",
    ) -> ModuleDescriptor:
        return ModuleDescriptor(
            name=name, version=version, enabled=enabled, status=status, description=description
        )

    @staticmethod
    def build_context(
        *,
        environment: str = "development",
        application_version: str = "0.1.0",
        request_id: str | None = None,
    ) -> PlatformContext:
        return PlatformContext(
            environment=environment, application_version=application_version, request_id=request_id
        )
