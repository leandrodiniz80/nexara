from typing import Any

from pydantic import BaseModel, Field

from app.application.use_cases.mission.mission_execution_summary import MissionExecutionSummary
from app.schemas.prospecting.prospect import ProspectRead


class CreateProspectingMissionResponse(BaseModel):
    """Output of CreateProspectingMissionUseCase.execute(). `prospects`/`assets` carry
    the full detail; `summary` carries the counts most callers actually want."""

    summary: MissionExecutionSummary
    prospects: list[ProspectRead] = Field(default_factory=list)
    assets: list[dict[str, Any]] = Field(default_factory=list)
