from app.platform.bootstrap.platform_service_catalog import PlatformServiceCatalog
from app.platform.bootstrap.platform_service_descriptor import PlatformServiceDescriptor


def build_platform_service_catalog(
    services: tuple[PlatformServiceDescriptor, ...],
) -> PlatformServiceCatalog:
    """Composition root for this catalog. Wires the given descriptors
    directly into a PlatformServiceCatalog — nothing else. Builds no
    default value of its own and integrates with nothing else in the
    platform.
    """
    return PlatformServiceCatalog(descriptors=services)
