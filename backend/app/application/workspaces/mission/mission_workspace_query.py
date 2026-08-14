import uuid

from pydantic import BaseModel


class MissionWorkspaceQuery(BaseModel):
    """Input to MissionWorkspaceService.load() — a Workspace is always addressed by
    the Mission it displays."""

    mission_id: uuid.UUID
