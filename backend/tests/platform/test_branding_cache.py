from dataclasses import replace

from app.platform.branding.branding_service import BrandingService
from app.platform.branding.branding_storage import InMemoryBrandingStorage
from app.platform.branding.nexara_theme import get_nexara_theme


def _theme_with_primary_bg(color: str):
    default = get_nexara_theme()
    return replace(default, colors=replace(default.colors, primary_bg=color))


def test_get_theme_retorna_mesmo_objeto_em_chamadas_repetidas():
    """A cache hit returns the exact cached reference — not just an equal
    value — so identity is a valid, if unusual, way to prove the cache path
    was taken rather than a fresh storage read.
    """
    storage = InMemoryBrandingStorage()
    service = BrandingService(storage=storage)

    theme1 = service.get_theme("org-a")
    theme2 = service.get_theme("org-a")

    assert theme1 is theme2


def test_set_theme_invalida_cache_forcando_nova_leitura():
    storage = InMemoryBrandingStorage()
    service = BrandingService(storage=storage)
    org = "org-1"

    theme1 = service.get_theme(org)  # caches the Nexara default

    service.set_theme(org, get_nexara_theme())

    theme2 = service.get_theme(org)  # must miss the (invalidated) cache

    assert theme1 is not theme2


def test_set_theme_reflete_no_get_theme_apos_invalidacao():
    storage = InMemoryBrandingStorage()
    service = BrandingService(storage=storage)
    org = "org-1"

    service.get_theme(org)  # warm the cache with the default
    service.set_theme(org, _theme_with_primary_bg("#ABCDEF"))

    assert service.get_theme(org).colors.primary_bg == "#ABCDEF"


def test_cache_e_isolado_por_organizacao():
    storage = InMemoryBrandingStorage()
    service = BrandingService(storage=storage)

    service.get_theme("org-a")  # warms org-a's cache entry only

    service.set_theme("org-b", _theme_with_primary_bg("#111111"))

    # org-a's cache entry must be untouched by an org-b write.
    assert service.get_theme("org-a") == get_nexara_theme()
    assert service.get_theme("org-b").colors.primary_bg == "#111111"


def test_cache_e_independente_entre_instancias_do_service():
    storage = InMemoryBrandingStorage()
    service1 = BrandingService(storage=storage)
    service2 = BrandingService(storage=storage)
    org = "org-1"

    service1.set_theme(org, _theme_with_primary_bg("#123456"))
    service1.get_theme(org)  # warms service1's own cache

    # service2 has never cached anything for org — must read from storage
    # (shared, so it sees service1's write) rather than any stale cache.
    assert service2.get_theme(org).colors.primary_bg == "#123456"


def test_get_theme_sem_organization_id_e_cacheavel_sem_erro():
    storage = InMemoryBrandingStorage()
    service = BrandingService(storage=storage)

    theme1 = service.get_theme(None)
    theme2 = service.get_theme(None)

    assert theme1 is theme2
    assert theme1 == get_nexara_theme()
