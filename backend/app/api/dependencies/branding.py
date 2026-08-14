from fastapi import Depends

from app.api.dependencies.auth import get_platform_container
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.branding.branding_service import BrandingService
from app.platform.branding.branding_storage import BrandingStorage, InMemoryBrandingStorage
from app.platform.branding.logo_storage import InMemoryLogoStorage, LogoStorage

_branding_storage: BrandingStorage | None = None
_logo_storage: LogoStorage | None = None


def get_branding_service(
    container: PlatformContainer = Depends(get_platform_container),
) -> BrandingService:
    """The storage backend is a module-level singleton (so custom themes persist
    across requests, same lifetime as `PlatformContainer`'s own singleton) —
    defaults to in-memory. `BrandingService` itself is built fresh per call so
    it always picks up the *current* (possibly test-overridden) container's
    audit trail, without needing to mutate a cached service's state.

    Deliberately does NOT reuse `container.storage`: that field is `None` by
    default (every test, and the real production container too, unless a
    caller explicitly configures Postgres/File storage) — routing branding
    through it would crash on the common case. `PlatformStorage.load()`/
    `save()` also replace one whole document per call, which is right for
    `PlatformAuth` but would silently clobber a different service's data if
    shared naively. Wiring a real `PostgresBrandingStorage` in is a deployment
    concern (construct one explicitly, or override this dependency) — not
    something the default resolution should attempt automatically.
    """
    global _branding_storage, _logo_storage

    if _branding_storage is None:
        _branding_storage = InMemoryBrandingStorage()

    if _logo_storage is None:
        _logo_storage = InMemoryLogoStorage()

    return BrandingService(
        storage=_branding_storage, audit=container.audit, logo_storage=_logo_storage
    )
