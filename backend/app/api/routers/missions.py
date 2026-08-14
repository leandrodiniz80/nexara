import uuid
from typing import Any

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel

from app.api.dependencies.application_services import get_mission_application_service
from app.api.dependencies.common import get_request_id
from app.api.docs.examples import START_MISSION_EXAMPLE
from app.api.responses.api_response import ApiResponse
from app.application.services.mission_application_service import MissionApplicationService
from app.application.use_cases.mission.create_prospecting_mission_request import (
    CreateProspectingMissionRequest,
)

router = APIRouter(prefix="/api/v1/missions", tags=["Mission"])


class MissionActorRequest(BaseModel):
    """Body for pause/resume — who's asking, purely for the audit trail
    (Mission.updated_by); no business meaning decided here."""

    updated_by: uuid.UUID | None = None


class CancelMissionRequest(MissionActorRequest):
    reason: str | None = None


@router.post("", response_model=ApiResponse[Any])
async def start_prospecting_mission(
    body: CreateProspectingMissionRequest = Body(
        openapi_examples={"expansao_goiania": START_MISSION_EXAMPLE}
    ),
    request_id: str = Depends(get_request_id),
    service: MissionApplicationService = Depends(get_mission_application_service),
) -> ApiResponse[Any]:
    result = await service.start_prospecting_mission(body)
    return ApiResponse.from_service_result(result, request_id=request_id)


@router.post("/{mission_id}/pause", response_model=ApiResponse[Any])
async def pause_mission(
    mission_id: uuid.UUID,
    body: MissionActorRequest = MissionActorRequest(),
    request_id: str = Depends(get_request_id),
    service: MissionApplicationService = Depends(get_mission_application_service),
) -> ApiResponse[Any]:
    result = await service.pause_mission(mission_id, updated_by=body.updated_by)
    return ApiResponse.from_service_result(result, request_id=request_id)


@router.post("/{mission_id}/resume", response_model=ApiResponse[Any])
async def resume_mission(
    mission_id: uuid.UUID,
    body: MissionActorRequest = MissionActorRequest(),
    request_id: str = Depends(get_request_id),
    service: MissionApplicationService = Depends(get_mission_application_service),
) -> ApiResponse[Any]:
    result = await service.resume_mission(mission_id, updated_by=body.updated_by)
    return ApiResponse.from_service_result(result, request_id=request_id)


@router.post("/{mission_id}/cancel", response_model=ApiResponse[Any])
async def cancel_mission(
    mission_id: uuid.UUID,
    body: CancelMissionRequest = CancelMissionRequest(),
    request_id: str = Depends(get_request_id),
    service: MissionApplicationService = Depends(get_mission_application_service),
) -> ApiResponse[Any]:
    result = await service.cancel_mission(
        mission_id, reason=body.reason, updated_by=body.updated_by
    )
    return ApiResponse.from_service_result(result, request_id=request_id)


@router.get("/{mission_id}", response_model=ApiResponse[Any])
async def get_mission_status(
    mission_id: uuid.UUID,
    request_id: str = Depends(get_request_id),
    service: MissionApplicationService = Depends(get_mission_application_service),
) -> ApiResponse[Any]:
    result = await service.get_status(mission_id)
    return ApiResponse.from_service_result(result, request_id=request_id)
