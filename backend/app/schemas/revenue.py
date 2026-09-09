from pydantic import BaseModel, Field


class RevenueSummaryResponse(BaseModel):
    """GET /revenue/summary — org-wide revenue snapshot, all values derived
    at read time from get_lead_estimated_value() (enrichment_data's
    company_size); nothing here is a stored column."""

    potential_revenue: float
    converted_revenue: float
    lost_revenue: float
    at_risk_revenue: float
    conversion_rate: float
    # Revenue-intelligence round, additive: the open (new + contacted)
    # pipeline's expected_value sum — probability-weighted, unlike
    # potential_revenue above (which is every non-lost lead's raw
    # estimated_value, un-adjusted for how likely it is to actually close).
    expected_pipeline_revenue: float = 0.0
    # Revenue-loop round — the Revenue Panel's own "breakdown por ação":
    # compute_revenue_attribution()'s revenue_by_action (scoring.py), the
    # same call/message/meeting attribution GET /workday/summary's
    # top_revenue_action is derived from, just exposed here in full rather
    # than collapsed to a single winner.
    revenue_by_action: dict[str, float] = Field(
        default_factory=lambda: {"call": 0.0, "message": 0.0, "meeting": 0.0}
    )


class RevenueTrendDay(BaseModel):
    """One day of GET /revenue/performance-trend. converted/lost are the
    estimated value of leads whose status changed to that value on this
    day (lead_status_history); created is the estimated value of leads
    whose created_at falls on this day. date is "YYYY-MM-DD"."""

    date: str
    converted: float
    lost: float
    created: float
