import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.crm.models.enums import OpportunityStatus


class CRMOpportunity(BaseModel):
    """One commercial deal in progress — mutable, like Job/WorkflowExecution:
    CRMEngine.move_stage() updates `stage_id`/`status`/`updated_at` on the same
    instance in place as it moves through its CRMPipeline.

    `company_id`/`contact_id`/`pipeline_id`/`stage_id` are all bare references,
    never the full entity embedded — this module's one consistent convention.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    company_id: uuid.UUID
    contact_id: uuid.UUID | None = None
    title: str
    pipeline_id: uuid.UUID
    stage_id: uuid.UUID
    status: OpportunityStatus = OpportunityStatus.OPEN
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)
