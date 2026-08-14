import uuid

from pydantic import BaseModel

from app.crm.models.crm_opportunity import CRMOpportunity
from app.crm.models.enums import OpportunityStatus


class OpportunitySummary(BaseModel):
    """A read-friendly view of a CRMOpportunity with its current stage's name
    resolved — sparing a caller from having to look the stage up itself."""

    id: uuid.UUID
    title: str
    company_id: uuid.UUID
    stage_name: str
    status: OpportunityStatus

    @classmethod
    def from_opportunity(
        cls, opportunity: CRMOpportunity, *, stage_name: str
    ) -> "OpportunitySummary":
        return cls(
            id=opportunity.id,
            title=opportunity.title,
            company_id=opportunity.company_id,
            stage_name=stage_name,
            status=opportunity.status,
        )
