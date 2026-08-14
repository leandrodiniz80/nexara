from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap


def build_default_platform_bootstrap() -> PlatformBootstrap:
    """Composition root for the Composition Root itself. PlatformBootstrap
    has no collaborators to inject — every dependency it ever builds comes
    lazily from its own methods — so this factory exists purely for
    consistency with every other official `build_default_*` factory in the
    platform.
    """
    return PlatformBootstrap()
