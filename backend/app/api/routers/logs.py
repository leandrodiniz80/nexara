import time

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies.auth import get_current_session, get_platform_container
from app.api.dependencies.common import get_request_id
from app.api.dependencies.tenant import get_request_tenant_id
from app.api.dependencies.tenant_context_guard import ensure_tenant_access
from app.api.responses.api_response import ApiResponse
from app.core.config import settings
from app.platform.bootstrap.platform_container import PlatformContainer

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/logs", tags=["Logs"])


@router.get("", response_model=ApiResponse[list[dict]])
async def get_logs(
    level: str | None = None,
    limit: int = 100,
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    request_id: str = Depends(get_request_id),
    tenant_id: str | None = Depends(get_request_tenant_id),
) -> ApiResponse[list[dict]]:
    start = time.perf_counter()

    auth = container.auth()
    role = auth.get_user_role(session["email"])
    organization_role = auth.get_user_organization_role(session["email"])

    if role != "admin" and organization_role != "owner":
        raise HTTPException(status_code=403, detail="Owner or admin role required")

    if organization_role != "owner":
        # Admin without ownership of this org: INFO-level only. Ownership (not
        # the "admin" role by itself) is what unlocks every level — an admin who
        # also happens to be the owner is unrestricted, per organization_role.
        if level is not None and level.upper() != "INFO":
            raise HTTPException(
                status_code=403, detail="Admins can only access INFO-level logs"
            )
        level = "INFO"

    if tenant_id is None:
        # Fail closed rather than falling back to unscoped/global data.
        logs = []
    else:
        ensure_tenant_access(session, tenant_id)
        logs = (
            container.logger.get_logs(level=level, organization_id=tenant_id, limit=limit)
            if container.logger is not None
            else []
        )

    return ApiResponse(
        success=True,
        data=logs,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )
