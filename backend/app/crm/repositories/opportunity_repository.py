import uuid

from app.crm.models.crm_opportunity import CRMOpportunity


class OpportunityRepository:
    """In-memory store of every CRMOpportunity."""

    def __init__(self) -> None:
        self._opportunities: dict[uuid.UUID, CRMOpportunity] = {}

    def save_opportunity(self, opportunity: CRMOpportunity) -> CRMOpportunity:
        self._opportunities[opportunity.id] = opportunity
        return opportunity

    def get_opportunity(self, opportunity_id: uuid.UUID) -> CRMOpportunity | None:
        return self._opportunities.get(opportunity_id)

    def list_opportunities(self, *, company_id: uuid.UUID | None = None) -> list[CRMOpportunity]:
        opportunities = list(self._opportunities.values())
        if company_id is not None:
            opportunities = [o for o in opportunities if o.company_id == company_id]
        return opportunities
