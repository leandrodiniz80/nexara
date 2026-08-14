import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.dependencies.auth import get_optional_session, get_platform_container
from app.api.dependencies.common import get_request_id
from app.api.dependencies.correlation import get_correlation_id
from app.api.dependencies.tenant import get_request_tenant_id
from app.api.dependencies.tenant_context_guard import ensure_tenant_access
from app.api.responses.api_response import ApiResponse
from app.core.config import settings
from app.platform.bootstrap.platform_container import PlatformContainer

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/read-models", tags=["Read Models"])


class ReadModelsSummary(BaseModel):
    service_names: list[str]
    version: str


class ReadModelsComparison(BaseModel):
    same_keys: bool
    same_length: bool
    differences: list[str]


@router.get("/v1", response_model=ApiResponse[ReadModelsSummary])
async def read_models_v1(
    request_id: str = Depends(get_request_id),
    container: PlatformContainer = Depends(get_platform_container),
    session: dict | None = Depends(get_optional_session),
    correlation_id: str = Depends(get_correlation_id),
    tenant_id: str | None = Depends(get_request_tenant_id),
) -> ApiResponse[ReadModelsSummary]:
    start = time.perf_counter()

    if session is not None:
        if tenant_id is not None:
            ensure_tenant_access(session, tenant_id)
        container.auth().check_rate_limit(session["email"], correlation_id=correlation_id)

    data = ReadModelsSummary(
        service_names=list(container.service_names()),
        version=container.read_models_v1_version(),
    )

    return ApiResponse(
        success=True,
        data=data,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/v2", response_model=ApiResponse[ReadModelsSummary])
async def read_models_v2(
    request_id: str = Depends(get_request_id),
    container: PlatformContainer = Depends(get_platform_container),
    session: dict | None = Depends(get_optional_session),
    correlation_id: str = Depends(get_correlation_id),
    tenant_id: str | None = Depends(get_request_tenant_id),
) -> ApiResponse[ReadModelsSummary]:
    start = time.perf_counter()

    if session is not None:
        if tenant_id is not None:
            ensure_tenant_access(session, tenant_id)
        container.auth().check_rate_limit(session["email"], correlation_id=correlation_id)

    v2 = container.read_models_v2()

    data = ReadModelsSummary(
        service_names=list(v2["service_names"]),
        version=container.read_models_version(),
    )

    return ApiResponse(
        success=True,
        data=data,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/compare", response_model=ApiResponse[ReadModelsComparison])
async def compare_read_models(
    request_id: str = Depends(get_request_id),
    container: PlatformContainer = Depends(get_platform_container),
    session: dict | None = Depends(get_optional_session),
    correlation_id: str = Depends(get_correlation_id),
    tenant_id: str | None = Depends(get_request_tenant_id),
) -> ApiResponse[ReadModelsComparison]:
    start = time.perf_counter()

    if session is not None:
        if tenant_id is not None:
            ensure_tenant_access(session, tenant_id)
        container.auth().check_rate_limit(session["email"], correlation_id=correlation_id)

    data = ReadModelsComparison(**container.compare_read_models_versions())

    return ApiResponse(
        success=True,
        data=data,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )
