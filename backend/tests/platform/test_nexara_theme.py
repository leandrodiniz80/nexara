import pytest

from app.platform.branding.design_tokens import ColorPalette, DesignTokens, Spacing, Typography
from app.platform.branding.nexara_theme import get_nexara_theme


def test_get_nexara_theme_retorna_design_tokens():
    theme = get_nexara_theme()

    assert isinstance(theme, DesignTokens)
    assert isinstance(theme.colors, ColorPalette)
    assert isinstance(theme.typography, Typography)
    assert isinstance(theme.spacing, Spacing)


def test_paleta_de_cores_correta():
    theme = get_nexara_theme()

    assert theme.colors.primary_bg == "#0B0F1A"
    assert theme.colors.secondary_bg == "#121826"
    assert theme.colors.border == "#1F2A44"
    assert theme.colors.text_primary == "#E6EAF2"
    assert theme.colors.text_secondary == "#9AA4BF"
    assert theme.colors.text_muted == "#6B7280"
    assert theme.colors.accent_primary == "#6366F1"
    assert theme.colors.accent_success == "#22C55E"
    assert theme.colors.accent_warning == "#F59E0B"
    assert theme.colors.accent_danger == "#EF4444"
    assert theme.colors.accent_info == "#3B82F6"
    assert theme.colors.gradient_main == "linear-gradient(135deg, #6366F1, #8B5CF6, #3B82F6)"


def test_tipografia_correta():
    theme = get_nexara_theme()

    assert theme.typography.font_family == "Inter, system-ui, sans-serif"
    assert theme.typography.font_size_base == 14
    assert theme.typography.font_weight_regular == 400
    assert theme.typography.font_weight_bold == 600


def test_spacing_correto():
    theme = get_nexara_theme()

    assert theme.spacing.xs == 4
    assert theme.spacing.sm == 8
    assert theme.spacing.md == 12
    assert theme.spacing.lg == 16
    assert theme.spacing.xl == 24


def test_get_nexara_theme_retorna_instancia_nova_a_cada_chamada():
    theme1 = get_nexara_theme()
    theme2 = get_nexara_theme()

    assert theme1 == theme2
    assert theme1 is not theme2


def test_design_tokens_sao_imutaveis():
    theme = get_nexara_theme()

    with pytest.raises((AttributeError, TypeError)):
        theme.colors.primary_bg = "#000000"

    with pytest.raises((AttributeError, TypeError)):
        theme.typography.font_size_base = 99

    with pytest.raises((AttributeError, TypeError)):
        theme.spacing.xs = 1


def test_cores_de_texto_e_fundo_sao_hex_validos():
    theme = get_nexara_theme()

    hex_colors = [
        theme.colors.primary_bg,
        theme.colors.secondary_bg,
        theme.colors.border,
        theme.colors.text_primary,
        theme.colors.text_secondary,
        theme.colors.text_muted,
        theme.colors.accent_primary,
        theme.colors.accent_success,
        theme.colors.accent_warning,
        theme.colors.accent_danger,
        theme.colors.accent_info,
    ]

    for color in hex_colors:
        assert color.startswith("#")
        assert len(color) == 7
        int(color[1:], 16)  # raises ValueError if not valid hex
