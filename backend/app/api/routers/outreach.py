import uuid
from typing import Any

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel

from app.api.dependencies.application_services import get_outreach_application_service
from app.api.dependencies.common import get_request_id
from app.api.docs.examples import OUTREACH_APPROVE_EXAMPLE, OUTREACH_GENERATE_EXAMPLE
from app.api.responses.api_response import ApiResponse
from app.application.services.outreach_application_service import OutreachApplicationService
from app.outreach.schemas.generation_request import GenerationRequest

router = APIRouter(prefix="/api/v1/outreach", tags=["Outreach"])


class AssetIdRequest(BaseModel):
    asset_id: uuid.UUID


class ApproveRequest(AssetIdRequest):
    approved_by: uuid.UUID | None = None


class RejectRequest(AssetIdRequest):
    reason: str | None = None


@router.post("/generate", response_model=ApiResponse[Any])
async def generate_outreach_asset(
    body: GenerationRequest = Body(openapi_examples={"follow_up": OUTREACH_GENERATE_EXAMPLE}),
    request_id: str = Depends(get_request_id),
    service: OutreachApplicationService = Depends(get_outreach_application_service),
) -> ApiResponse[Any]:
    result = await service.generate_asset(body)
    return ApiResponse.from_service_result(result, request_id=request_id)


@router.post("/submit", response_model=ApiResponse[Any])
async def submit_outreach_asset_for_approval(
    body: AssetIdRequest,
    request_id: str = Depends(get_request_id),
    service: OutreachApplicationService = Depends(get_outreach_application_service),
) -> ApiResponse[Any]:
    result = await service.submit_for_approval(body.asset_id)
    return ApiResponse.from_service_result(result, request_id=request_id)


@router.post("/approve", response_model=ApiResponse[Any])
async def approve_outreach_asset(
    body: ApproveRequest = Body(openapi_examples={"approve_pending": OUTREACH_APPROVE_EXAMPLE}),
    request_id: str = Depends(get_request_id),
    service: OutreachApplicationService = Depends(get_outreach_application_service),
) -> ApiResponse[Any]:
    result = await service.approve(body.asset_id, approved_by=body.approved_by)
    return ApiResponse.from_service_result(result, request_id=request_id)


@router.post("/reject", response_model=ApiResponse[Any])
async def reject_outreach_asset(
    body: RejectRequest,
    request_id: str = Depends(get_request_id),
    service: OutreachApplicationService = Depends(get_outreach_application_service),
) -> ApiResponse[Any]:
    result = await service.reject(body.asset_id, reason=body.reason)
    return ApiResponse.from_service_result(result, request_id=request_id)
