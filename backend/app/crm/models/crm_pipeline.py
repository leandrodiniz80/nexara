import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.crm.models.crm_stage import CRMStage


class CRMPipeline(BaseModel):
    """A named, ordered sequence of CRMStages — the definition, not any single
    opportunity's journey through it. Frozen, same reasoning as Workflow: built
    once by PipelineBuilder, never mutated in place.
    """

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    stages: list[CRMStage] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
