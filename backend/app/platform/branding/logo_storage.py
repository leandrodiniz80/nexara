class LogoStorage:
    """Plain class with no-op defaults, not an ABC — matching every other
    pluggable storage interface in this platform (`PlatformStorage`,
    `PlatformCache`, `BrandingStorage`), none of which use `abc.ABC`.
    Deliberately knows nothing about HTTP routes/URLs: that's the router's
    concern, not storage's — same layering as `BrandingStorage` never
    returning a URL from `save_version()`.
    """

    def save_logo(self, organization_id: str, content: bytes, content_type: str) -> None:
        pass

    def get_logo(self, organization_id: str) -> tuple[bytes, str] | None:
        return None


class InMemoryLogoStorage(LogoStorage):
    def __init__(self):
        self._logos: dict[str, tuple[bytes, str]] = {}

    def save_logo(self, organization_id: str, content: bytes, content_type: str) -> None:
        self._logos[organization_id] = (content, content_type)

    def get_logo(self, organization_id: str) -> tuple[bytes, str] | None:
        return self._logos.get(organization_id)
