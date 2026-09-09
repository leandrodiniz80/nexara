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


class RevenueForecastResponse(BaseModel):
    """GET /revenue/forecast — Autonomous-sales-OS round. Distinct from
    RevenueSummaryResponse.expected_pipeline_revenue above: that one is a
    plain sum of score_leads()'s own win_probability-weighted expected_value
    over new+contacted leads; this one additionally applies a forecasting-
    specific decay (compute_forecast_value(), scoring.py — overdue *0.6,
    idle >3 days *0.7, otherwise unchanged) on top, since a stalling deal's
    plain expected_value overstates how much of that money will actually
    land this period. today_expected sums the decayed value over leads due
    today or already overdue; week_expected/month_expected are both the
    same decayed total across every active lead — week_expected discounted
    by 0.8 (the prompt's own factor: a week captures less of the full
    pipeline's eventual close than a month does), month_expected the full
    total. confidence is the mean win_probability (0-1) across those same
    active leads — 0.0 with none."""

    today_expected: float = 0.0
    week_expected: float = 0.0
    month_expected: float = 0.0
    confidence: float = 0.0


class RevenueTrendDay(BaseModel):
    """One day of GET /revenue/performance-trend. converted/lost are the
    estimated value of leads whose status changed to that value on this
    day (lead_status_history); created is the estimated value of leads
    whose created_at falls on this day. date is "YYYY-MM-DD"."""

    date: str
    converted: float
    lost: float
    created: float
