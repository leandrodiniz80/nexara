import time

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.dependencies.auth import get_platform_container
from app.api.dependencies.billing import get_stripe_service
from app.api.responses.api_response import ApiResponse
from app.platform.billing.stripe_service import StripeService
from app.platform.bootstrap.platform_container import PlatformContainer

router = APIRouter(tags=["Health"])

_STARTED_AT = time.monotonic()
API_VERSION = "1.0.0"


class HealthStatus(BaseModel):
    status: str
    version: str
    uptime: float
    components: dict[str, str] = Field(default_factory=dict)


@router.get("/", response_model=ApiResponse[dict[str, str]])
async def root(request: Request) -> ApiResponse[dict[str, str]]:
    """Friendly landing response for the bare root path — there was no
    registered route there at all before, so it fell through to a plain
    404. Doesn't replace /health as the real liveness check."""
    return ApiResponse(
        success=True,
        data={"status": "NEXARA ONLINE \U0001f680"},
        request_id=getattr(request.state, "request_id", "unknown"),
        execution_time=0.0,
    )


@router.get("/health", response_model=ApiResponse[HealthStatus])
async def health(
    request: Request,
    container: PlatformContainer = Depends(get_platform_container),
    stripe_service: StripeService | None = Depends(get_stripe_service),
) -> ApiResponse[HealthStatus]:
    """Liveness check — reports the process's own status/version/uptime, plus a
    cheap, non-blocking read of which optional components (storage/cache/Stripe)
    are plugged in. Never calls out to any of them, just checks presence."""
    start = time.perf_counter()

    components = {
        "auth": "ok",
        "storage": "ok" if container.storage is not None else "disabled",
        "cache": "ok" if container.cache is not None else "disabled",
        "stripe": "ok" if stripe_service is not None else "disabled",
    }

    data = HealthStatus(
        status="ok",
        version=API_VERSION,
        uptime=time.monotonic() - _STARTED_AT,
        components=components,
    )
    return ApiResponse(
        success=True,
        data=data,
        request_id=getattr(request.state, "request_id", "unknown"),
        execution_time=time.perf_counter() - start,
    )
