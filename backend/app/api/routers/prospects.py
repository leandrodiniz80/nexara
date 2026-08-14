import uuid
from typing import Any

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel

from app.api.dependencies.application_services import get_prospect_application_service
from app.api.dependencies.common import get_request_id
from app.api.docs.examples import GENERATE_ASSET_EXAMPLE, QUALIFY_PROSPECT_EXAMPLE
from app.api.responses.api_response import ApiResponse
from app.application.services.prospect_application_service import ProspectApplicationService
from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.schemas.prospecting.company import CompanyRead

router = APIRouter(prefix="/api/v1/prospects", tags=["Prospects"])


class QualifyRequest(BaseModel):
    profile: CommercialProfile
    mission_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None
    requested_by: uuid.UUID | None = None


class GenerateAssetRequest(BaseModel):
    company: CompanyRead
    asset_type: str
    channel: str | None = None
    tone: str | None = None
    contact_name: str | None = None
    objective: str | None = None
    mission_id: uuid.UUID | None = None
    requested_by: uuid.UUID | None = None


class ApproveAssetRequest(BaseModel):
    asset_id: uuid.UUID
    approved_by: uuid.UUID | None = None


class RejectAssetRequest(BaseModel):
    asset_id: uuid.UUID
    reason: str | None = None


@router.post("/{prospect_id}/qualify", response_model=ApiResponse[Any])
async def qualify_prospect(
    prospect_id: uuid.UUID,
    body: QualifyRequest = Body(openapi_examples={"retail_company": QUALIFY_PROSPECT_EXAMPLE}),
    request_id: str = Depends(get_request_id),
    service: ProspectApplicationService = Depends(get_prospect_application_service),
) -> ApiResponse[Any]:
    result = await service.qualify(
        body.profile,
        mission_id=body.mission_id,
        company_id=body.company_id,
        prospect_id=prospect_id,
        requested_by=body.requested_by,
    )
    return ApiResponse.from_service_result(result, request_id=request_id)


@router.post("/{prospect_id}/generate-asset", response_model=ApiResponse[Any])
async def generate_prospect_asset(
    prospect_id: uuid.UUID,
    body: GenerateAssetRequest = Body(
        openapi_examples={"agencia_xyz_email": GENERATE_ASSET_EXAMPLE}
    ),
    request_id: str = Depends(get_request_id),
    service: ProspectApplicationService = Depends(get_prospect_application_service),
) -> ApiResponse[Any]:
    result = await service.generate_asset(
        prospect_id=prospect_id,
        company=body.company,
        asset_type=body.asset_type,
        channel=body.channel,
        tone=body.tone,
        contact_name=body.contact_name,
        objective=body.objective,
        mission_id=body.mission_id,
        requested_by=body.requested_by,
    )
    return ApiResponse.from_service_result(result, request_id=request_id)


@router.post("/{prospect_id}/approve-asset", response_model=ApiResponse[Any])
async def approve_prospect_asset(
    prospect_id: uuid.UUID,
    body: ApproveAssetRequest,
    request_id: str = Depends(get_request_id),
    service: ProspectApplicationService = Depends(get_prospect_application_service),
) -> ApiResponse[Any]:
    # `prospect_id` identifies which prospect's page this action came from (URL
    # convention); the asset being approved is always addressed by its own id, per
    # ProspectApplicationService.approve_asset()'s existing (frozen) signature.
    del prospect_id
    result = await service.approve_asset(body.asset_id, approved_by=body.approved_by)
    return ApiResponse.from_service_result(result, request_id=request_id)


@router.post("/{prospect_id}/reject-asset", response_model=ApiResponse[Any])
async def reject_prospect_asset(
    prospect_id: uuid.UUID,
    body: RejectAssetRequest,
    request_id: str = Depends(get_request_id),
    service: ProspectApplicationService = Depends(get_prospect_application_service),
) -> ApiResponse[Any]:
    del prospect_id
    result = await service.reject_asset(body.asset_id, reason=body.reason)
    return ApiResponse.from_service_result(result, request_id=request_id)
