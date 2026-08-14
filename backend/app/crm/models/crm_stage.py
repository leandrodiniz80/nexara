import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.crm.models.enums import OpportunityStatus


class CRMStage(BaseModel):
    """One stage of a CRMPipeline — the definition, not an opportunity's current
    position (that's CRMOpportunity.stage_id). Frozen: PipelineBuilder always
    produces a fresh CRMStage rather than mutating one in place, the same
    "definition is immutable" reasoning as WorkflowStep.

    `outcome` defaults to OPEN for every stage except the pipeline's terminal ones
    (e.g. "Fechado" -> WON, "Perdido" -> LOST) — moving an opportunity into a stage
    is what sets its status, there is no separate close action.
    """

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    order: int
    outcome: OpportunityStatus = OpportunityStatus.OPEN
