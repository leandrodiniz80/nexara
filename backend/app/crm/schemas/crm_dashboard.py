from pydantic import BaseModel, Field


class CRMDashboard(BaseModel):
    """A snapshot of the whole CRM's commercial health — what CRMEngine.get_dashboard()
    returns."""

    total_companies: int
    total_contacts: int
    total_opportunities: int
    by_stage: dict[str, int] = Field(default_factory=dict)
    won: int
    lost: int
    conversion_rate: float
