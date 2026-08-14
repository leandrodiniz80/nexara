from dataclasses import replace

from app.platform.branding.branding_service import BrandingService
from app.platform.branding.nexara_theme import get_nexara_theme


def _theme_with_primary_bg(color: str):
    default = get_nexara_theme()
    return replace(default, colors=replace(default.colors, primary_bg=color))


def test_get_theme_sem_organization_id_retorna_nexara_default():
    service = BrandingService()

    theme = service.get_theme(None)

    assert theme == get_nexara_theme()


def test_get_theme_organizacao_desconhecida_retorna_nexara_default():
    service = BrandingService()

    theme = service.get_theme("org-ghost")

    assert theme == get_nexara_theme()


def test_set_theme_depois_get_theme_retorna_o_tema_customizado():
    service = BrandingService()

    service.set_theme("org-a", _theme_with_primary_bg("#FF0000"))

    assert service.get_theme("org-a").colors.primary_bg == "#FF0000"


def test_set_theme_isolado_entre_organizacoes():
    service = BrandingService()

    service.set_theme("org-a", _theme_with_primary_bg("#111111"))
    service.set_theme("org-b", _theme_with_primary_bg("#222222"))

    assert service.get_theme("org-a").colors.primary_bg == "#111111"
    assert service.get_theme("org-b").colors.primary_bg == "#222222"


def test_org_sem_tema_customizado_nao_afetada_por_outra_organizacao():
    service = BrandingService()

    service.set_theme("org-a", _theme_with_primary_bg("#111111"))

    assert service.get_theme("org-b") == get_nexara_theme()


def test_set_theme_sobrescreve_tema_anterior_da_mesma_organizacao():
    service = BrandingService()

    service.set_theme("org-a", _theme_with_primary_bg("#111111"))
    service.set_theme("org-a", _theme_with_primary_bg("#999999"))

    assert service.get_theme("org-a").colors.primary_bg == "#999999"
