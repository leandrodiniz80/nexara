from app.platform.bootstrap.platform_bootstrap_factory import build_default_platform_bootstrap
from app.platform.bootstrap.platform_container import PlatformContainer


def build_default_platform_container() -> PlatformContainer:
    """Composition root for this container. Builds its one collaborator
    exclusively through its own official factory,
    `build_default_platform_bootstrap()`, and wires it into a
    PlatformContainer — nothing else.
    """
    return PlatformContainer(bootstrap=build_default_platform_bootstrap())
