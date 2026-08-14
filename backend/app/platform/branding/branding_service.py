import hashlib
import json

from app.platform.audit.platform_audit import PlatformAudit
from app.platform.branding.branding_storage import BrandingStorage, InMemoryBrandingStorage
from app.platform.branding.design_tokens import (
    ColorPalette,
    DesignTokens,
    Layout,
    Spacing,
    Typography,
)
from app.platform.branding.logo_storage import InMemoryLogoStorage, LogoStorage
from app.platform.branding.nexara_theme import get_nexara_theme


def _to_payload(theme: DesignTokens) -> dict:
    return {
        "colors": theme.colors.__dict__,
        "typography": theme.typography.__dict__,
        "spacing": theme.spacing.__dict__,
        "layout": theme.layout.__dict__,
    }


def _from_payload(payload: dict) -> DesignTokens:
    kwargs = {
        "colors": ColorPalette(**payload["colors"]),
        "typography": Typography(**payload["typography"]),
        "spacing": Spacing(**payload["spacing"]),
    }

    # Records saved before Sprint 232 have no "layout" key — DesignTokens'
    # own default layout kicks in, same backward-compat guarantee as the
    # dataclass itself.
    if "layout" in payload:
        kwargs["layout"] = Layout(**payload["layout"])

    return DesignTokens(**kwargs)


class BrandingService:
    def __init__(
        self,
        storage: BrandingStorage | None = None,
        audit: PlatformAudit | None = None,
        logo_storage: LogoStorage | None = None,
    ) -> None:
        self._storage = storage or InMemoryBrandingStorage()
        self._audit = audit
        self._logo_storage = logo_storage or InMemoryLogoStorage()
        # Keyed by organization_id (like _storage itself) — never a single
        # "current tenant" pointer, so concurrent reads for different orgs
        # never interfere with each other.
        self._cache: dict[str | None, DesignTokens] = {}
        # Keyed by content hash (Sprint 234) — a theme's hash IS its cache
        # key, so this is naturally content-addressed and safe to share
        # across organizations that happen to produce identical CSS.
        self._css_cache: dict[str, str] = {}

    def get_theme(self, organization_id: str | None) -> DesignTokens:
        if organization_id in self._cache:
            return self._cache[organization_id]

        if not organization_id:
            theme = get_nexara_theme()
        else:
            record = self._storage.load_latest(organization_id)
            theme = _from_payload(record["payload"]) if record is not None else get_nexara_theme()

        self._cache[organization_id] = theme

        return theme

    def set_theme(self, organization_id: str, theme: DesignTokens) -> None:
        record = self._storage.save_version(organization_id, _to_payload(theme))

        self.invalidate_cache(organization_id)

        if self._audit is not None:
            self._audit.log_event(
                "branding_updated", None, organization_id, {"version": record["version"]}
            )

    def get_versions(self, organization_id: str) -> list[dict]:
        return self._storage.list_versions(organization_id)

    def set_logo(self, organization_id: str, content: bytes, content_type: str) -> None:
        self._logo_storage.save_logo(organization_id, content, content_type)

        if self._audit is not None:
            self._audit.log_event(
                "logo_updated", None, organization_id, {"content_type": content_type}
            )

    def get_logo(self, organization_id: str) -> tuple[bytes, str] | None:
        return self._logo_storage.get_logo(organization_id)

    def has_logo(self, organization_id: str | None) -> bool:
        if not organization_id:
            return False

        return self._logo_storage.get_logo(organization_id) is not None

    def invalidate_cache(self, organization_id: str | None) -> None:
        self._cache.pop(organization_id, None)
        # Clearing the whole CSS cache (rather than just this org's hash) is
        # a deliberate simplification: other orgs' entries stay keyed by
        # their own unchanged hash and get rebuilt identically on next
        # access, so this only costs a cache miss, never incorrect content.
        self._css_cache.clear()

    def get_css_by_hash(self, organization_id: str | None) -> tuple[str, str]:
        """Returns (theme_hash, css) for the given tenant, generating and
        caching the CSS on first computation."""
        theme_hash = self.get_theme_hash(organization_id)

        if theme_hash in self._css_cache:
            return theme_hash, self._css_cache[theme_hash]

        theme = self.get_theme(organization_id)
        css = self.to_css(theme)
        self._css_cache[theme_hash] = css

        return theme_hash, css

    def get_css_by_content_hash(self, theme_hash: str) -> str | None:
        """Pure content-addressed lookup — no tenant/auth involved at all.
        This is what makes `/branding/css/{hash}` genuinely servable by a CDN
        edge node or an anonymous `<link>` tag, neither of which carries a
        bearer token: the hash itself is the only key needed. Only returns a
        hit for a hash some prior `get_css_by_hash()` call already computed.
        """
        return self._css_cache.get(theme_hash)

    def get_theme_hash(self, organization_id: str | None) -> str:
        """MD5 is fine here — this is an ETag/cache-validation fingerprint, not
        a security boundary (collision resistance isn't required; the worst
        case is a stale cache being treated as fresh)."""
        theme = self.get_theme(organization_id)
        payload = _to_payload(theme)
        raw = json.dumps(payload, sort_keys=True).encode()

        return hashlib.md5(raw).hexdigest()

    def to_css(self, theme: DesignTokens) -> str:
        c = theme.colors
        t = theme.typography
        s = theme.spacing
        layout = theme.layout

        return f"""\
:root {{
  --color-primary-bg: {c.primary_bg};
  --color-secondary-bg: {c.secondary_bg};
  --color-border: {c.border};

  --color-text-primary: {c.text_primary};
  --color-text-secondary: {c.text_secondary};
  --color-text-muted: {c.text_muted};

  --color-accent-primary: {c.accent_primary};
  --color-accent-success: {c.accent_success};
  --color-accent-warning: {c.accent_warning};
  --color-accent-danger: {c.accent_danger};
  --color-accent-info: {c.accent_info};

  --gradient-main: {c.gradient_main};

  --font-family: {t.font_family};
  --font-mono: {t.mono_family};
  --font-weight-regular: {t.font_weight_regular};
  --font-weight-bold: {t.font_weight_bold};

  --radius: {layout.border_radius}px;
  --shadow-sm: {layout.shadow_sm};
  --shadow-md: {layout.shadow_md};
  --shadow-lg: {layout.shadow_lg};

  --space-xs: {s.xs}px;
  --space-sm: {s.sm}px;
  --space-md: {s.md}px;
  --space-lg: {s.lg}px;
  --space-xl: {s.xl}px;
}}""".strip()
