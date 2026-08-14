from dataclasses import replace

from app.platform.branding.branding_service import BrandingService
from app.platform.branding.branding_storage import InMemoryBrandingStorage
from app.platform.branding.nexara_theme import get_nexara_theme


def _theme_with_primary_bg(color: str):
    default = get_nexara_theme()
    return replace(default, colors=replace(default.colors, primary_bg=color))


def test_hash_e_estavel_para_o_mesmo_tema():
    service = BrandingService()

    assert service.get_theme_hash(None) == service.get_theme_hash(None)


def test_hash_muda_apos_customizacao():
    storage = InMemoryBrandingStorage()
    service = BrandingService(storage=storage)

    before = service.get_theme_hash("org-a")
    service.set_theme("org-a", _theme_with_primary_bg("#123456"))
    after = service.get_theme_hash("org-a")

    assert before != after


def test_hash_diferente_entre_organizacoes_com_temas_diferentes():
    storage = InMemoryBrandingStorage()
    service = BrandingService(storage=storage)

    service.set_theme("org-a", _theme_with_primary_bg("#111111"))
    service.set_theme("org-b", _theme_with_primary_bg("#222222"))

    assert service.get_theme_hash("org-a") != service.get_theme_hash("org-b")


def test_hash_igual_para_organizacoes_sem_customizacao():
    storage = InMemoryBrandingStorage()
    service = BrandingService(storage=storage)

    assert service.get_theme_hash("org-a") == service.get_theme_hash("org-b")


def test_hash_e_string_hexadecimal():
    service = BrandingService()

    digest = service.get_theme_hash(None)

    assert isinstance(digest, str)
    assert len(digest) == 32
    int(digest, 16)  # raises ValueError if not valid hex
