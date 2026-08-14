import uuid
from typing import ClassVar

from app.application.services.application_service_result import ApplicationServiceResult
from app.application.services.base_application_service import BaseApplicationService
from app.application.use_cases.mission.create_prospecting_mission import (
    CreateProspectingMissionUseCase,
)
from app.application.use_cases.mission.create_prospecting_mission_request import (
    CreateProspectingMissionRequest,
)
from app.application.workspaces.mission.mission_workspace_query import MissionWorkspaceQuery
from app.application.workspaces.mission.mission_workspace_service import MissionWorkspaceService
from app.schemas.mission.mission import MissionRead
from app.services.mission.mission_engine import MissionEngine


class MissionApplicationService(BaseApplicationService):
    """Single entry point for everything Mission-related. Coordinates
    CreateProspectingMissionUseCase for the full "start a mission" flow, and
    MissionEngine directly for the individual lifecycle transitions no existing Use
    Case wraps (pause/resume/cancel) — MissionEngine is an existing, frozen domain
    engine, not a Repository, so calling it directly here doesn't violate "no direct
    Repository access"; fetching the Mission this engine needs to transition is done
    through `mission_engine.repository`, the same "reach through an already-injected
    Engine's own collaborator" pattern CopyTask established for OutreachEngine in
    Sprint 11 — never an independently-injected Repository of this service's own.
    """

    service_name: ClassVar[str] = "mission_application_service"

    def __init__(
        self,
        create_prospecting_mission_use_case: CreateProspectingMissionUseCase,
        mission_engine: MissionEngine,
        mission_workspace_service: MissionWorkspaceService,
    ) -> None:
        super().__init__()
        self.create_prospecting_mission_use_case = create_prospecting_mission_use_case
        self.mission_engine = mission_engine
        self.mission_workspace_service = mission_workspace_service

    async def start_prospecting_mission(
        self, request: CreateProspectingMissionRequest
    ) -> ApplicationServiceResult:
        async def _operation():
            if not request.mission_name.strip():
                raise ValueError("mission_name must not be blank.")
            if not request.segment.strip():
                raise ValueError("segment must not be blank.")
            return await self.create_prospecting_mission_use_case.execute(request)

        return await self._run("start_prospecting_mission", _operation)

    async def pause_mission(
        self, mission_id: uuid.UUID, *, updated_by: uuid.UUID | None = None
    ) -> ApplicationServiceResult:
        async def _operation():
            mission = await self._get_mission(mission_id)
            mission = await self.mission_engine.pause(mission, updated_by=updated_by)
            return MissionRead.model_validate(mission)

        return await self._run("pause_mission", _operation)

    async def resume_mission(
        self, mission_id: uuid.UUID, *, updated_by: uuid.UUID | None = None
    ) -> ApplicationServiceResult:
        async def _operation():
            mission = await self._get_mission(mission_id)
            mission = await self.mission_engine.resume(mission, updated_by=updated_by)
            return MissionRead.model_validate(mission)

        return await self._run("resume_mission", _operation)

    async def cancel_mission(
        self,
        mission_id: uuid.UUID,
        *,
        reason: str | None = None,
        updated_by: uuid.UUID | None = None,
    ) -> ApplicationServiceResult:
        async def _operation():
            mission = await self._get_mission(mission_id)
            mission = await self.mission_engine.cancel(
                mission, reason=reason, updated_by=updated_by
            )
            return MissionRead.model_validate(mission)

        return await self._run("cancel_mission", _operation)

    async def get_status(self, mission_id: uuid.UUID) -> ApplicationServiceResult:
        async def _operation():
            workspace = await self.mission_workspace_service.load(
                MissionWorkspaceQuery(mission_id=mission_id)
            )
            if workspace is None:
                raise LookupError(f"Mission {mission_id} not found.")
            return workspace

        return await self._run("get_status", _operation)

    async def _get_mission(self, mission_id: uuid.UUID):
        mission = await self.mission_engine.repository.get_by_id(mission_id)
        if mission is None:
            raise LookupError(f"Mission {mission_id} not found.")
        return mission
