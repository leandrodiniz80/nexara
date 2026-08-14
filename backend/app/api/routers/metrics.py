import time

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies.auth import get_current_session, get_platform_container
from app.api.dependencies.common import get_request_id
from app.api.dependencies.tenant import get_request_tenant_id
from app.api.dependencies.tenant_context_guard import ensure_tenant_access
from app.api.responses.api_response import ApiResponse
from app.core.config import settings
from app.platform.bootstrap.platform_container import PlatformContainer

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/metrics", tags=["Metrics"])


@router.get("", response_model=ApiResponse[dict])
async def get_metrics(
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    request_id: str = Depends(get_request_id),
    tenant_id: str | None = Depends(get_request_tenant_id),
) -> ApiResponse[dict]:
    start = time.perf_counter()

    auth = container.auth()
    role = auth.get_user_role(session["email"])
    organization_role = auth.get_user_organization_role(session["email"])

    if role != "admin" and organization_role != "owner":
        raise HTTPException(status_code=403, detail="Owner or admin role required")

    if tenant_id is None:
        # Fail closed rather than falling back to unscoped/global data.
        metrics = {}
    else:
        ensure_tenant_access(session, tenant_id)
        metrics = (
            container.metrics.get_metrics(organization_id=tenant_id)
            if container.metrics is not None
            else {}
        )

    return ApiResponse(
        success=True,
        data={"metrics": metrics},
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )
