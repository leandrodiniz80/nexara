import time

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.api.dependencies.auth import get_current_session, get_platform_container
from app.api.dependencies.branding import get_branding_service
from app.api.dependencies.common import get_request_id
from app.api.dependencies.tenant import get_request_tenant_id
from app.api.dependencies.tenant_context_guard import ensure_tenant_access
from app.api.dependencies.tenant_resolver import (
    DomainTenantResolver,
    get_domain_tenant_resolver,
    get_tenant_id_from_domain,
)
from app.api.responses.api_response import ApiResponse
from app.core.config import settings
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.branding.branding_service import BrandingService, _from_payload
from app.platform.branding.design_tokens import (
    ColorPalette,
    DesignTokens,
    Layout,
    Spacing,
    Typography,
)

_CACHE_CONTROL = "public, max-age=300"
_ALLOWED_LOGO_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/svg+xml",
    "image/webp",
    "image/gif",
}

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/branding", tags=["Branding"])


class ColorPaletteResponse(BaseModel):
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


class TypographyResponse(BaseModel):
    font_family: str
    font_size_base: int
    font_weight_regular: int
    font_weight_bold: int
    mono_family: str


class SpacingResponse(BaseModel):
    xs: int
    sm: int
    md: int
    lg: int
    xl: int


class LayoutResponse(BaseModel):
    border_radius: int
    shadow_sm: str
    shadow_md: str
    shadow_lg: str


class ThemeResponse(BaseModel):
    colors: ColorPaletteResponse
    typography: TypographyResponse
    spacing: SpacingResponse
    layout: LayoutResponse


class BrandingResponse(BaseModel):
    name: str
    tenant_id: str | None = None
    theme: ThemeResponse
    css_url: str
    logo_url: str | None = None


# Request models mirror the response models field-for-field on purpose: a
# custom org theme is a drop-in replacement for the default Nexara theme, so
# it has to speak the exact same schema — anything else would force a
# frontend to handle two incompatible color shapes depending on whether an
# org has custom branding.
class ColorPaletteRequest(BaseModel):
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


class TypographyRequest(BaseModel):
    font_family: str
    font_size_base: int
    font_weight_regular: int
    font_weight_bold: int
    # Optional (Sprint 232) — existing payloads without it still validate;
    # Typography's own default fills in when omitted.
    mono_family: str | None = None


class SpacingRequest(BaseModel):
    xs: int
    sm: int
    md: int
    lg: int
    xl: int


class LayoutRequest(BaseModel):
    border_radius: int
    shadow_sm: str
    shadow_md: str
    shadow_lg: str


class SetBrandingRequest(BaseModel):
    colors: ColorPaletteRequest
    typography: TypographyRequest
    spacing: SpacingRequest
    # Optional (Sprint 232) — existing payloads without it still validate;
    # DesignTokens' own default layout fills in when omitted.
    layout: LayoutRequest | None = None


class BrandingVersionResponse(BaseModel):
    version: int
    theme: ThemeResponse
    created_at: str


def _to_theme_response(tokens: DesignTokens) -> ThemeResponse:
    return ThemeResponse(
        colors=ColorPaletteResponse(**tokens.colors.__dict__),
        typography=TypographyResponse(**tokens.typography.__dict__),
        spacing=SpacingResponse(**tokens.spacing.__dict__),
        layout=LayoutResponse(**tokens.layout.__dict__),
    )


def _css_url_for(branding: BrandingService, tenant_id: str | None) -> str:
    theme_hash, _ = branding.get_css_by_hash(tenant_id)

    return f"{settings.API_V1_PREFIX}/branding/css/{theme_hash}"


def _logo_url_for(branding: BrandingService, tenant_id: str | None) -> str | None:
    if not branding.has_logo(tenant_id):
        return None

    return f"{settings.API_V1_PREFIX}/branding/logo/{tenant_id}"


def _to_response(
    tokens: DesignTokens,
    tenant_id: str | None,
    css_url: str,
    logo_url: str | None,
) -> BrandingResponse:
    return BrandingResponse(
        name="Nexara",
        tenant_id=tenant_id,
        theme=_to_theme_response(tokens),
        css_url=css_url,
        logo_url=logo_url,
    )


@router.get("", response_model=ApiResponse[BrandingResponse])
async def get_branding(
    request_id: str = Depends(get_request_id),
    tenant_id: str | None = Depends(get_request_tenant_id),
    branding: BrandingService = Depends(get_branding_service),
) -> ApiResponse[BrandingResponse]:
    """Public — no auth required. A frontend needs branding/theme before a user
    is ever authenticated (e.g. to style its own login page). When a valid
    session resolves a tenant, its custom theme is used if one was set;
    otherwise (including for anonymous callers) the default Nexara theme.
    """
    start = time.perf_counter()

    tokens = branding.get_theme(tenant_id)
    data = _to_response(
        tokens, tenant_id, _css_url_for(branding, tenant_id), _logo_url_for(branding, tenant_id)
    )

    return ApiResponse(
        success=True,
        data=data,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.post("/custom", response_model=ApiResponse[BrandingResponse])
async def set_branding(
    body: SetBrandingRequest,
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    request_id: str = Depends(get_request_id),
    tenant_id: str | None = Depends(get_request_tenant_id),
    branding: BrandingService = Depends(get_branding_service),
) -> ApiResponse[BrandingResponse]:
    start = time.perf_counter()

    if tenant_id is None:
        raise HTTPException(status_code=404, detail="No organization found")

    ensure_tenant_access(session, tenant_id)

    organization_role = container.auth().get_user_organization_role(session["email"])
    if organization_role != "owner":
        raise HTTPException(
            status_code=403, detail="Only the organization owner can customize branding"
        )

    theme_kwargs = {
        "colors": ColorPalette(**body.colors.model_dump()),
        # exclude_none: mono_family is optional — omitting it lets
        # Typography's own default fill in, instead of overwriting it with
        # an explicit None.
        "typography": Typography(**body.typography.model_dump(exclude_none=True)),
        "spacing": Spacing(**body.spacing.model_dump()),
    }
    if body.layout is not None:
        theme_kwargs["layout"] = Layout(**body.layout.model_dump())

    theme = DesignTokens(**theme_kwargs)
    branding.set_theme(tenant_id, theme)

    data = _to_response(
        theme, tenant_id, _css_url_for(branding, tenant_id), _logo_url_for(branding, tenant_id)
    )

    return ApiResponse(
        success=True,
        data=data,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/versions", response_model=ApiResponse[list[BrandingVersionResponse]])
async def get_branding_versions(
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    request_id: str = Depends(get_request_id),
    tenant_id: str | None = Depends(get_request_tenant_id),
    branding: BrandingService = Depends(get_branding_service),
) -> ApiResponse[list[BrandingVersionResponse]]:
    """Owner-only — same access model as `/custom`: whoever can change
    branding is who gets to see its history.
    """
    start = time.perf_counter()

    if tenant_id is None:
        raise HTTPException(status_code=404, detail="No organization found")

    ensure_tenant_access(session, tenant_id)

    organization_role = container.auth().get_user_organization_role(session["email"])
    if organization_role != "owner":
        raise HTTPException(
            status_code=403, detail="Only the organization owner can view branding history"
        )

    data = [
        BrandingVersionResponse(
            version=record["version"],
            theme=_to_theme_response(_from_payload(record["payload"])),
            created_at=record["created_at"],
        )
        for record in branding.get_versions(tenant_id)
    ]

    return ApiResponse(
        success=True,
        data=data,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


class PublicBrandingResponse(BaseModel):
    """Deliberately NOT wrapped in `ApiResponse` — this is the "simple, direct"
    frontend-consumption shape (e.g. a lightweight fetch that doesn't want to
    unwrap `data.data...`), distinct on purpose from `/branding`'s typed,
    enveloped, internal-consumption shape. `/branding` itself is unchanged.
    """

    name: str
    colors: ColorPaletteResponse
    typography: TypographyResponse
    layout: LayoutResponse
    css_url: str
    logo_url: str | None = None


@router.get("/public", response_model=PublicBrandingResponse)
async def get_public_branding(
    tenant_id: str | None = Depends(get_request_tenant_id),
    branding: BrandingService = Depends(get_branding_service),
) -> PublicBrandingResponse:
    """Public — no auth required, same tenant-resolution/fallback rules as
    `/branding`."""
    tokens = branding.get_theme(tenant_id)

    return PublicBrandingResponse(
        name="Nexara",
        colors=ColorPaletteResponse(**tokens.colors.__dict__),
        typography=TypographyResponse(**tokens.typography.__dict__),
        layout=LayoutResponse(**tokens.layout.__dict__),
        css_url=_css_url_for(branding, tenant_id),
        logo_url=_logo_url_for(branding, tenant_id),
    )


@router.get("/css", response_class=PlainTextResponse)
async def get_branding_css(
    request: Request,
    tenant_id: str | None = Depends(get_request_tenant_id),
    branding: BrandingService = Depends(get_branding_service),
):
    """Public — no auth required. Ready to `<link rel="stylesheet">` or fetch
    as text; not JSON, so no response model/envelope applies. Contract
    unchanged since Sprint 233 — still returns raw, tenant-resolved CSS with
    an ETag/304 for session-aware clients. `/branding/css/{hash}` (Sprint
    234) is the separate, purely content-addressed sibling for CDN/anonymous
    consumption; this endpoint now shares its CSS-string cache internally
    (a request for unchanged content no longer re-renders the template).
    """
    etag, css = branding.get_css_by_hash(tenant_id)
    headers = {"ETag": etag, "Cache-Control": _CACHE_CONTROL}

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)

    return PlainTextResponse(content=css, headers=headers)


@router.get("/css/{theme_hash}", response_class=PlainTextResponse)
async def get_branding_css_by_hash(
    theme_hash: str, branding: BrandingService = Depends(get_branding_service)
):
    """Public, content-addressed, no tenant/auth resolution at all — the hash
    IS the lookup key. This is what makes the URL genuinely servable by a CDN
    edge node or an anonymous `<link>` tag, neither of which carries a
    bearer token. Immutable: the same hash always serves the same bytes, so
    the response is cacheable forever. Only resolves a hash some prior
    `/branding`, `/branding/public`, `/branding/domain` or `/branding/css`
    call has already computed (in-memory cache — lost on restart, same
    "evolves later" scope as the rest of this sprint's storage).
    """
    css = branding.get_css_by_content_hash(theme_hash)

    if css is None:
        raise HTTPException(status_code=404, detail="CSS not found")

    return PlainTextResponse(
        content=css,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


class DomainBrandingResponse(BaseModel):
    """Same "simple, direct" shape as `/public` — deliberately not wrapped in
    `ApiResponse`, since this is the CDN/white-label-facing endpoint."""

    name: str
    tenant_id: str | None
    theme: ThemeResponse
    css_url: str
    logo_url: str | None = None


@router.get("/domain", response_model=DomainBrandingResponse)
async def get_branding_by_domain(
    request: Request,
    tenant_id: str | None = Depends(get_tenant_id_from_domain),
    branding: BrandingService = Depends(get_branding_service),
):
    """Public — no auth required, resolves the tenant from the request's Host
    header instead of a bearer token, for true white-label consumption (a
    domain not registered to any organization falls back to the default
    Nexara theme, same as an anonymous caller elsewhere in this router).
    ETag-validated and cacheable, CDN-ready.
    """
    etag, _ = branding.get_css_by_hash(tenant_id)
    headers = {"ETag": etag, "Cache-Control": _CACHE_CONTROL}

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)

    theme = branding.get_theme(tenant_id)

    return Response(
        content=DomainBrandingResponse(
            name="Nexara",
            tenant_id=tenant_id,
            theme=_to_theme_response(theme),
            css_url=f"{settings.API_V1_PREFIX}/branding/css/{etag}",
            logo_url=_logo_url_for(branding, tenant_id),
        ).model_dump_json(),
        media_type="application/json",
        headers=headers,
    )


@router.post("/logo", response_model=ApiResponse[dict])
async def upload_branding_logo(
    file: UploadFile = File(...),
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    request_id: str = Depends(get_request_id),
    tenant_id: str | None = Depends(get_request_tenant_id),
    branding: BrandingService = Depends(get_branding_service),
) -> ApiResponse[dict]:
    """Owner-only — same access model as `/custom`: whoever can change
    branding is who gets to set the logo.
    """
    start = time.perf_counter()

    if tenant_id is None:
        raise HTTPException(status_code=404, detail="No organization found")

    ensure_tenant_access(session, tenant_id)

    organization_role = container.auth().get_user_organization_role(session["email"])
    if organization_role != "owner":
        raise HTTPException(
            status_code=403, detail="Only the organization owner can upload a logo"
        )

    if file.content_type not in _ALLOWED_LOGO_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported logo content type")

    content = await file.read()
    branding.set_logo(tenant_id, content, file.content_type)

    return ApiResponse(
        success=True,
        data={"logo_url": _logo_url_for(branding, tenant_id)},
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/logo/{organization_id}")
async def get_branding_logo(
    organization_id: str, branding: BrandingService = Depends(get_branding_service)
):
    """Public, no auth — a company logo is meant to be displayed anywhere,
    same reasoning already applied to `/branding/css/{hash}`. The raw path
    param carries no tenant-isolation risk: it only ever reveals the logo
    that organization itself uploaded, nothing else.
    """
    logo = branding.get_logo(organization_id)

    if logo is None:
        raise HTTPException(status_code=404, detail="Logo not found")

    content, content_type = logo

    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


class RegisterDomainRequest(BaseModel):
    domain: str


@router.post("/domain/register", response_model=ApiResponse[dict])
async def register_branding_domain(
    body: RegisterDomainRequest,
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    request_id: str = Depends(get_request_id),
    tenant_id: str | None = Depends(get_request_tenant_id),
    resolver: DomainTenantResolver = Depends(get_domain_tenant_resolver),
) -> ApiResponse[dict]:
    """Owner-only — same access model as `/custom`. The organization is always
    the caller's own session-resolved tenant (never taken from the request
    body): accepting an arbitrary organization_id in the payload would let
    any authenticated owner point a domain at a DIFFERENT organization.
    """
    start = time.perf_counter()

    if tenant_id is None:
        raise HTTPException(status_code=404, detail="No organization found")

    ensure_tenant_access(session, tenant_id)

    organization_role = container.auth().get_user_organization_role(session["email"])
    if organization_role != "owner":
        raise HTTPException(
            status_code=403, detail="Only the organization owner can register a domain"
        )

    domain = body.domain.lower()
    existing_owner = resolver.get_owner(domain)
    if existing_owner is not None and existing_owner != tenant_id:
        raise HTTPException(
            status_code=409, detail="Domain already registered to another organization"
        )

    resolver.register_domain(domain, tenant_id)

    return ApiResponse(
        success=True,
        data={"domain": domain, "organization_id": tenant_id},
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )
