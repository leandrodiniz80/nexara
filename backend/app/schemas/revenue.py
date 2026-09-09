from pydantic import BaseModel


class RevenueSummaryResponse(BaseModel):
    """GET /revenue/summary — org-wide revenue snapshot, all values derived
    at read time from get_lead_estimated_value() (enrichment_data's
    company_size); nothing here is a stored column."""

    potential_revenue: float
    converted_revenue: float
    lost_revenue: float
    at_risk_revenue: float
    conversion_rate: float


class RevenueTrendDay(BaseModel):
    """One day of GET /revenue/performance-trend. converted/lost are the
    estimated value of leads whose status changed to that value on this
    day (lead_status_history); created is the estimated value of leads
    whose created_at falls on this day. date is "YYYY-MM-DD"."""

    date: str
    converted: float
    lost: float
    created: float
