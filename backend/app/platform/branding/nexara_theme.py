from app.platform.branding.design_tokens import (
    ColorPalette,
    DesignTokens,
    Layout,
    Spacing,
    Typography,
)


def get_nexara_theme() -> DesignTokens:
    return DesignTokens(
        colors=ColorPalette(
            primary_bg="#0B0F1A",
            secondary_bg="#121826",
            border="#1F2A44",
            text_primary="#E6EAF2",
            text_secondary="#9AA4BF",
            text_muted="#6B7280",
            accent_primary="#6366F1",
            accent_success="#22C55E",
            accent_warning="#F59E0B",
            accent_danger="#EF4444",
            accent_info="#3B82F6",
            gradient_main="linear-gradient(135deg, #6366F1, #8B5CF6, #3B82F6)",
        ),
        typography=Typography(
            font_family="Inter, system-ui, sans-serif",
            font_size_base=14,
            font_weight_regular=400,
            font_weight_bold=600,
            mono_family="JetBrains Mono, monospace",
        ),
        spacing=Spacing(xs=4, sm=8, md=12, lg=16, xl=24),
        layout=Layout(
            border_radius=8,
            shadow_sm="0 1px 2px rgba(0,0,0,0.05)",
            shadow_md="0 4px 6px rgba(0,0,0,0.1)",
            shadow_lg="0 10px 15px rgba(0,0,0,0.15)",
        ),
    )
