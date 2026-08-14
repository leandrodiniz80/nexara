import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.dependencies.auth import get_current_session, get_platform_container
from app.api.dependencies.common import get_request_id
from app.api.dependencies.tenant import get_request_tenant_id
from app.api.dependencies.tenant_context_guard import ensure_tenant_access
from app.api.responses.api_response import ApiResponse
from app.core.config import settings
from app.platform.bootstrap.platform_container import PlatformContainer

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/org", tags=["Organizations"])


class OrganizationSummary(BaseModel):
    organization_id: str
    name: str
    user_count: int


@router.get("/me", response_model=ApiResponse[OrganizationSummary])
async def my_organization(
    session: dict = Depends(get_current_session),
    request_id: str = Depends(get_request_id),
    container: PlatformContainer = Depends(get_platform_container),
    tenant_id: str | None = Depends(get_request_tenant_id),
) -> ApiResponse[OrganizationSummary]:
    start = time.perf_counter()

    if tenant_id is None:
        raise HTTPException(status_code=404, detail="No organization found")

    ensure_tenant_access(session, tenant_id)

    org = container.auth().get_organization(tenant_id)

    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    data = OrganizationSummary(
        organization_id=tenant_id,
        name=org["name"],
        user_count=len(org["users"]),
    )

    return ApiResponse(
        success=True,
        data=data,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )
