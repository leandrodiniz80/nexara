import uuid
from typing import Any

from fastapi import APIRouter, Depends

from app.api.dependencies.application_services import get_workspace_application_service
from app.api.dependencies.common import get_request_id
from app.api.docs.examples import MISSION_WORKSPACE_EXAMPLE
from app.api.responses.api_response import ApiResponse
from app.application.services.workspace_application_service import WorkspaceApplicationService

router = APIRouter(prefix="/api/v1/workspace", tags=["Workspace"])


_WORKSPACE_RESPONSE_EXAMPLE = {
    "content": {"application/json": {"example": MISSION_WORKSPACE_EXAMPLE["value"]}}
}


@router.get(
    "/missions/{mission_id}",
    response_model=ApiResponse[Any],
    responses={200: _WORKSPACE_RESPONSE_EXAMPLE},
)
async def load_mission_workspace(
    mission_id: uuid.UUID,
    request_id: str = Depends(get_request_id),
    service: WorkspaceApplicationService = Depends(get_workspace_application_service),
) -> ApiResponse[Any]:
    result = await service.load_mission_workspace(mission_id)
    return ApiResponse.from_service_result(result, request_id=request_id)
