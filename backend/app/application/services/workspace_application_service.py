import uuid
from typing import Any, ClassVar

from app.application.services.application_service_result import ApplicationServiceResult
from app.application.services.base_application_service import BaseApplicationService
from app.application.workspaces.mission.mission_workspace_query import MissionWorkspaceQuery
from app.application.workspaces.mission.mission_workspace_service import MissionWorkspaceService


class WorkspaceApplicationService(BaseApplicationService):
    """Single entry point for read-only workspace views. `load_mission_workspace()`
    is a direct pass-through to MissionWorkspaceService.load() (Sprint 13) — the
    workspace layer already produces exactly the shape a caller needs.

    `load_prospect_workspace()` has no dedicated ProspectWorkspaceService to call
    into (this sprint may not create new domain-level services) — it's implemented
    as a filter over an already-loaded MissionWorkspace instead: no new Repository
    access, no new business logic, just picking out the one prospect (and its
    assets) a caller asked for. Because of that, it needs `mission_id` as well as
    `prospect_id` — there is no existing, allowed way to resolve one from the other.
    """

    service_name: ClassVar[str] = "workspace_application_service"

    def __init__(self, mission_workspace_service: MissionWorkspaceService) -> None:
        super().__init__()
        self.mission_workspace_service = mission_workspace_service

    async def load_mission_workspace(self, mission_id: uuid.UUID) -> ApplicationServiceResult:
        async def _operation():
            workspace = await self.mission_workspace_service.load(
                MissionWorkspaceQuery(mission_id=mission_id)
            )
            if workspace is None:
                raise LookupError(f"Mission {mission_id} not found.")
            return workspace

        return await self._run("load_mission_workspace", _operation)

    async def load_prospect_workspace(
        self, mission_id: uuid.UUID, prospect_id: uuid.UUID
    ) -> ApplicationServiceResult:
        async def _operation() -> dict[str, Any]:
            workspace = await self.mission_workspace_service.load(
                MissionWorkspaceQuery(mission_id=mission_id)
            )
            if workspace is None:
                raise LookupError(f"Mission {mission_id} not found.")
            prospect = next((p for p in workspace.prospects if p.id == prospect_id), None)
            if prospect is None:
                raise LookupError(f"Prospect {prospect_id} not found in mission {mission_id}.")
            assets = [asset for asset in workspace.assets if asset.prospect_id == prospect_id]
            return {
                "mission": workspace.mission,
                "prospect": prospect,
                "assets": assets,
                "recommendations": workspace.recommendations,
            }

        return await self._run("load_prospect_workspace", _operation)
