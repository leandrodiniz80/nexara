import time

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies.auth import get_current_session, get_platform_container
from app.api.dependencies.common import get_request_id
from app.api.dependencies.correlation import get_correlation_id
from app.api.dependencies.tenant import get_request_tenant_id
from app.api.dependencies.tenant_context_guard import ensure_tenant_access
from app.api.responses.api_response import ApiResponse
from app.core.config import settings
from app.platform.bootstrap.platform_container import PlatformContainer

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/secure", tags=["Security"])


@router.get("/test-auth", response_model=ApiResponse[dict])
async def test_auth(
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    request_id: str = Depends(get_request_id),
    correlation_id: str = Depends(get_correlation_id),
    tenant_id: str | None = Depends(get_request_tenant_id),
) -> ApiResponse[dict]:
    start = time.perf_counter()

    if tenant_id is not None:
        ensure_tenant_access(session, tenant_id)

    container.auth().check_rate_limit(session["email"], correlation_id=correlation_id)

    return ApiResponse(
        success=True,
        data={"email": session["email"], "tenant_id": tenant_id},
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/test-role", response_model=ApiResponse[dict])
async def test_role(
    role: str,
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    request_id: str = Depends(get_request_id),
    correlation_id: str = Depends(get_correlation_id),
    tenant_id: str | None = Depends(get_request_tenant_id),
) -> ApiResponse[dict]:
    start = time.perf_counter()

    if tenant_id is not None:
        ensure_tenant_access(session, tenant_id)

    container.auth().check_rate_limit(session["email"], correlation_id=correlation_id)

    actual_role = container.auth().get_user_role(session["email"])

    if actual_role != role:
        raise HTTPException(status_code=403, detail=f"Role '{role}' required")

    return ApiResponse(
        success=True,
        data={"email": session["email"], "role": actual_role, "tenant_id": tenant_id},
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/test-permission", response_model=ApiResponse[dict])
async def test_permission(
    permission: str,
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    request_id: str = Depends(get_request_id),
    correlation_id: str = Depends(get_correlation_id),
    tenant_id: str | None = Depends(get_request_tenant_id),
) -> ApiResponse[dict]:
    start = time.perf_counter()

    if tenant_id is not None:
        ensure_tenant_access(session, tenant_id)

    container.auth().check_rate_limit(session["email"], correlation_id=correlation_id)

    permissions = container.auth().get_user_permissions(session["email"])

    if permission not in permissions:
        raise HTTPException(status_code=403, detail=f"Permission '{permission}' required")

    return ApiResponse(
        success=True,
        data={"email": session["email"], "permissions": permissions, "tenant_id": tenant_id},
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )
