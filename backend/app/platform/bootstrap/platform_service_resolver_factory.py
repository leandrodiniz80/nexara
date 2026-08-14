from app.platform.bootstrap.platform_service_registry import PlatformServiceRegistry
from app.platform.bootstrap.platform_service_resolver import PlatformServiceResolver


def build_default_platform_service_resolver(
    *, registry: PlatformServiceRegistry
) -> PlatformServiceResolver:
    """Composition root for this resolver. PlatformServiceResolver has
    exactly one collaborator — the PlatformServiceRegistry it resolves
    against — and this factory exists so callers (PlatformBootstrap
    included) never construct it directly.
    """
    return PlatformServiceResolver(registry=registry)
