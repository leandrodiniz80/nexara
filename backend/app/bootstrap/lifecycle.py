from app.bootstrap.bootstrap import Bootstrap
from app.bootstrap.service_locator import ServiceLocator
from app.config.settings import PlatformSettings

_active_bootstrap: Bootstrap | None = None


def initialize(settings: PlatformSettings | None = None) -> ServiceLocator:
    """The platform's single process-level entrypoint: builds every enabled
    module exactly once and returns a read-only ServiceLocator over the
    result. Intended for future executables (CLI, FastAPI, Worker, Scheduler,
    main.py) — no existing module calls this. With no `settings` given,
    Bootstrap itself loads PlatformSettings' own defaults — the same
    zero-argument behavior this function has always had.
    """
    global _active_bootstrap
    bootstrap = Bootstrap(settings)
    locator = bootstrap.initialize()
    _active_bootstrap = bootstrap
    return locator


def shutdown() -> None:
    """Tears down whatever initialize() last built. A no-op if nothing was
    initialized yet."""
    global _active_bootstrap
    if _active_bootstrap is not None:
        _active_bootstrap.shutdown()
        _active_bootstrap = None
