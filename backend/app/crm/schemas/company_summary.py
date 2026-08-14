import uuid

from pydantic import BaseModel

from app.crm.models.crm_company import CRMCompany


class CompanySummary(BaseModel):
    """A read-friendly view of a CRMCompany plus counts a caller would otherwise
    have to compute itself from the Contact/Opportunity repositories."""

    id: uuid.UUID
    name: str
    total_contacts: int
    total_opportunities: int

    @classmethod
    def from_company(
        cls, company: CRMCompany, *, total_contacts: int, total_opportunities: int
    ) -> "CompanySummary":
        return cls(
            id=company.id,
            name=company.name,
            total_contacts=total_contacts,
            total_opportunities=total_opportunities,
        )
