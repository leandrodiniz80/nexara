import hmac
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from app.api.dependencies.auth import (
    get_current_session,
    get_optional_session,
    get_platform_container,
)
from app.api.dependencies.common import get_request_id
from app.api.dependencies.correlation import get_correlation_id
from app.api.responses.api_response import ApiResponse
from app.core.config import settings
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.rate_limit.platform_rate_limiter import PlatformRateLimiter

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/auth", tags=["Auth"])

logger = logging.getLogger("app.api.auth")

MIN_PASSWORD_LENGTH = 8
# Fields that decide *where* and *with what power* an account lands. Only a
# platform admin may set them; anyone else always gets a fresh organization
# they own, with role "user" and no extra permissions.
_PRIVILEGED_REGISTER_FIELDS = ("role", "permissions", "organization_id", "organization_role")
# Every non-admin sign-up attempt counts — including ones with a wrong invite
# token — so guessing the token is throttled too. Per-IP limit plus a global
# cap (X-Forwarded-For can be spoofed to dodge the per-IP bucket, the global
# one can't). In-memory: right for the single backend replica we run today.
_REGISTER_PER_IP_LIMIT, _REGISTER_PER_IP_WINDOW_SECONDS = 5, 60
_REGISTER_GLOBAL_LIMIT, _REGISTER_GLOBAL_WINDOW_SECONDS = 30, 3600
_register_rate_limiter = PlatformRateLimiter()

_REGISTRATION_CLOSED = "Cadastro disponível apenas por convite."


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    role: str = "user"
    permissions: list[str] = Field(default_factory=list)
    organization_id: str | None = None
    organization_role: str = "member"


class LoginRequest(BaseModel):
    email: str
    password: str


class SessionResponse(BaseModel):
    token: str
    email: str


class MeResponse(BaseModel):
    email: str
    role: str | None
    permissions: list[str]
    organization_id: str | None


def _is_valid_invite_token(provided: str | None) -> bool:
    expected = settings.REGISTRATION_INVITE_TOKEN
    if not expected or not provided:
        return False
    return hmac.compare_digest(provided.encode(), expected.encode())


def _client_ip(request: Request) -> str:
    # Behind Railway's proxy request.client is the proxy itself; the first
    # X-Forwarded-For hop is the real client (spoofable — see the global cap).
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_register_rate_limit(request: Request) -> None:
    ip_ok = _register_rate_limiter.allow(
        f"register:ip:{_client_ip(request)}",
        _REGISTER_PER_IP_LIMIT,
        _REGISTER_PER_IP_WINDOW_SECONDS,
    )
    global_ok = _register_rate_limiter.allow(
        "register:global", _REGISTER_GLOBAL_LIMIT, _REGISTER_GLOBAL_WINDOW_SECONDS
    )
    if not (ip_ok and global_ok):
        logger.warning("auth.register.rate_limited ip=%s", _client_ip(request))
        raise HTTPException(
            status_code=429, detail="Muitas tentativas. Tente novamente mais tarde."
        )


@router.post("/register", response_model=ApiResponse[None])
async def register(
    body: RegisterRequest,
    request: Request,
    request_id: str = Depends(get_request_id),
    container: PlatformContainer = Depends(get_platform_container),
    correlation_id: str = Depends(get_correlation_id),
    session: dict | None = Depends(get_optional_session),
) -> ApiResponse[None]:
    """Invite-only account creation (settings.REGISTRATION_MODE == "invite",
    the production default). Allowed callers: an authenticated platform
    admin (full control over every field), or anyone presenting the
    configured invite token in X-Invite-Token — who always gets a brand-new
    organization they own and can't set role/permissions/organization_*.
    Previously this route was public and trusted those fields, so anyone
    could create accounts at will, or join an existing organization as its
    owner just by sending its organization_id.

    Non-admin attempts are rate limited and answered with one generic
    message whatever the reason (no token, wrong token, privileged field),
    so the route reveals nothing about how it's configured.

    REGISTRATION_MODE == "open" keeps the old anonymous behavior for the
    automated test suite only. In both modes, granting role="admin" still
    requires an admin caller once any admin exists (the very first admin of
    a fresh deployment remains a bootstrap gap has_any_admin() accepts).
    """
    start = time.perf_counter()
    auth = container.auth()
    caller_is_admin = session is not None and auth.get_user_role(session["email"]) == "admin"

    if settings.REGISTRATION_MODE == "invite":
        if not caller_is_admin:
            _check_register_rate_limit(request)
            privileged = [f for f in _PRIVILEGED_REGISTER_FIELDS if f in body.model_fields_set]
            if not _is_valid_invite_token(request.headers.get("X-Invite-Token")) or privileged:
                logger.warning(
                    "auth.register.denied ip=%s privileged_fields=%s",
                    _client_ip(request),
                    privileged,
                )
                raise HTTPException(status_code=403, detail=_REGISTRATION_CLOSED)

        if len(body.password) < MIN_PASSWORD_LENGTH:
            raise HTTPException(
                status_code=422,
                detail=f"A senha deve ter pelo menos {MIN_PASSWORD_LENGTH} caracteres.",
            )

    if auth.exists(body.email):
        raise HTTPException(status_code=409, detail="User already exists")

    if body.role == "admin":
        if not caller_is_admin and auth.has_any_admin():
            raise HTTPException(
                status_code=403, detail="Only an existing admin can create another admin"
            )

    container.auth().register_user(
        body.email,
        body.password,
        role=body.role,
        permissions=body.permissions,
        organization_id=body.organization_id,
        organization_role=body.organization_role,
        correlation_id=correlation_id,
    )

    return ApiResponse(
        success=True,
        data=None,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.post("/login", response_model=ApiResponse[SessionResponse])
async def login(
    body: LoginRequest,
    request_id: str = Depends(get_request_id),
    container: PlatformContainer = Depends(get_platform_container),
    correlation_id: str = Depends(get_correlation_id),
) -> ApiResponse[SessionResponse]:
    start = time.perf_counter()

    container.auth().check_rate_limit(body.email, correlation_id=correlation_id)

    session = container.auth().login(body.email, body.password, correlation_id=correlation_id)

    if session is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return ApiResponse(
        success=True,
        data=SessionResponse(**session),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.post("/logout", response_model=ApiResponse[None])
async def logout(
    session: dict = Depends(get_current_session),
    request_id: str = Depends(get_request_id),
    container: PlatformContainer = Depends(get_platform_container),
) -> ApiResponse[None]:
    start = time.perf_counter()

    container.auth().logout(session["token"])

    return ApiResponse(
        success=True,
        data=None,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/me", response_model=ApiResponse[MeResponse])
async def me(
    session: dict = Depends(get_current_session),
    request_id: str = Depends(get_request_id),
    container: PlatformContainer = Depends(get_platform_container),
) -> ApiResponse[MeResponse]:
    start = time.perf_counter()

    email = session["email"]
    auth = container.auth()

    data = MeResponse(
        email=email,
        role=auth.get_user_role(email),
        permissions=auth.get_user_permissions(email),
        organization_id=auth.get_user_organization(email),
    )

    return ApiResponse(
        success=True,
        data=data,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )
