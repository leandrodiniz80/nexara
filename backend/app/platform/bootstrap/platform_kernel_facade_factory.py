from app.platform.bootstrap.platform_container_factory import build_default_platform_container
from app.platform.bootstrap.platform_kernel_facade import PlatformKernelFacade


def build_default_platform_kernel_facade() -> PlatformKernelFacade:
    """Composition root for this facade. Builds its one collaborator
    exclusively through its own official factory,
    `build_default_platform_container()`, and wires it into a
    PlatformKernelFacade — nothing else.
    """
    return PlatformKernelFacade(container=build_default_platform_container())
