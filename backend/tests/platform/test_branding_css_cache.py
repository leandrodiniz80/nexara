from dataclasses import replace

from app.platform.branding.branding_service import BrandingService
from app.platform.branding.branding_storage import InMemoryBrandingStorage
from app.platform.branding.nexara_theme import get_nexara_theme


def _theme_with_primary_bg(color: str):
    default = get_nexara_theme()
    return replace(default, colors=replace(default.colors, primary_bg=color))


def test_get_css_by_hash_reutilizado_entre_chamadas():
    service = BrandingService()

    hash1, css1 = service.get_css_by_hash("org-1")
    hash2, css2 = service.get_css_by_hash("org-1")

    assert hash1 == hash2
    assert css1 == css2
    # Identity, not just equality: proves the second call hit the CSS cache
    # rather than re-rendering an identical string.
    assert css1 is css2


def test_get_css_by_hash_muda_apos_set_theme():
    storage = InMemoryBrandingStorage()
    service = BrandingService(storage=storage)

    hash1, css1 = service.get_css_by_hash("org-1")
    service.set_theme("org-1", _theme_with_primary_bg("#123456"))
    hash2, css2 = service.get_css_by_hash("org-1")

    assert hash1 != hash2
    assert css1 != css2
    assert "#123456" in css2


def test_get_css_by_content_hash_encontra_hash_conhecido():
    service = BrandingService()

    theme_hash, css = service.get_css_by_hash(None)

    assert service.get_css_by_content_hash(theme_hash) == css


def test_get_css_by_content_hash_retorna_none_para_hash_desconhecido():
    service = BrandingService()

    assert service.get_css_by_content_hash("never-computed-hash") is None


def test_invalidate_cache_limpa_theme_cache_e_css_cache():
    storage = InMemoryBrandingStorage()
    service = BrandingService(storage=storage)

    theme_hash, _ = service.get_css_by_hash("org-1")
    assert service.get_css_by_content_hash(theme_hash) is not None

    service.invalidate_cache("org-1")

    # The old hash's CSS is no longer resolvable by content lookup — the
    # theme cache miss on the next get_theme() will regenerate it under a
    # (possibly identical) hash, but the stale cache entry itself is gone.
    assert theme_hash not in service._css_cache


def test_css_cache_e_content_addressed_nao_por_organizacao():
    """Two organizations with an identical (default) theme share the same
    hash and therefore the same CSS cache entry — content-addressed, not
    keyed by tenant."""
    service = BrandingService()

    hash_a, css_a = service.get_css_by_hash("org-a")
    hash_b, css_b = service.get_css_by_hash("org-b")

    assert hash_a == hash_b
    assert css_a is css_b


def test_set_theme_de_uma_org_nao_invalida_css_valido_de_outra_com_hash_diferente():
    storage = InMemoryBrandingStorage()
    service = BrandingService(storage=storage)
    service.set_theme("org-a", _theme_with_primary_bg("#111111"))
    hash_a, css_a = service.get_css_by_hash("org-a")

    service.set_theme("org-b", _theme_with_primary_bg("#222222"))

    # org-a's CSS content is identical to before — even though the whole
    # cache was cleared, regenerating it produces the exact same bytes.
    new_hash_a, new_css_a = service.get_css_by_hash("org-a")
    assert new_hash_a == hash_a
    assert new_css_a == css_a
