from dataclasses import dataclass


@dataclass(frozen=True)
class ColorPalette:
    primary_bg: str
    secondary_bg: str
    border: str

    text_primary: str
    text_secondary: str
    text_muted: str

    accent_primary: str
    accent_success: str
    accent_warning: str
    accent_danger: str
    accent_info: str

    gradient_main: str


@dataclass(frozen=True)
class Typography:
    font_family: str
    font_size_base: int
    font_weight_regular: int
    font_weight_bold: int
    # Additive, defaulted (Sprint 232) — existing 4-arg construction still works.
    mono_family: str = "JetBrains Mono, monospace"


@dataclass(frozen=True)
class Spacing:
    xs: int
    sm: int
    md: int
    lg: int
    xl: int


@dataclass(frozen=True)
class Layout:
    border_radius: int
    shadow_sm: str
    shadow_md: str
    shadow_lg: str


_DEFAULT_LAYOUT = Layout(
    border_radius=8,
    shadow_sm="0 1px 2px rgba(0,0,0,0.05)",
    shadow_md="0 4px 6px rgba(0,0,0,0.1)",
    shadow_lg="0 10px 15px rgba(0,0,0,0.15)",
)


@dataclass(frozen=True)
class DesignTokens:
    colors: ColorPalette
    typography: Typography
    spacing: Spacing
    # Additive, defaulted (Sprint 232) — existing 3-arg construction still works.
    layout: Layout = _DEFAULT_LAYOUT
