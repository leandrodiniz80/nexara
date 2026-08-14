import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

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

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/auth", tags=["Auth"])


class RegisterRequest(BaseModel):
    email: str
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


@router.post("/register", response_model=ApiResponse[None])
async def register(
    body: RegisterRequest,
    request_id: str = Depends(get_request_id),
    container: PlatformContainer = Depends(get_platform_container),
    correlation_id: str = Depends(get_correlation_id),
    session: dict | None = Depends(get_optional_session),
) -> ApiResponse[None]:
    """Self-registration is otherwise fully open (no invite/approval gate
    for regular accounts) — but `role` is a client-supplied field with no
    other check, so once any admin exists on the platform, granting
    `role="admin"` here requires the caller to already BE an authenticated
    admin. Without this, anyone on the internet could grant themselves
    admin at any time just by registering a new account with the right
    field set. The very first admin in a fresh deployment is still
    whichever request gets there first with `role="admin"` — a narrower
    bootstrap gap `PlatformAuth.has_any_admin()` accepts, not something
    this endpoint alone can fully close.
    """
    start = time.perf_counter()

    if container.auth().exists(body.email):
        raise HTTPException(status_code=409, detail="User already exists")

    if body.role == "admin":
        auth = container.auth()
        caller_is_admin = (
            session is not None and auth.get_user_role(session["email"]) == "admin"
        )

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
