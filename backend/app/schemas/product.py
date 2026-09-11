import uuid

from pydantic import BaseModel


class BiggestOpportunity(BaseModel):
    """compute_product_summary()'s own pick (product-consolidation round)
    — the single highest expected_value lead still open in whatever
    rank_leads_by_priority() already scored for this request. None when
    every lead is converted/lost."""

    lead_id: uuid.UUID
    name: str
    company_name: str | None = None
    expected_value: int


class ProductSummaryResponse(BaseModel):
    """GET /product/summary — the Revenue Decision System's single "explain
    it in seconds" view (Task 2/3, product-consolidation round). Every
    field here is pure aggregation of a figure some other endpoint already
    computes — see compute_product_summary()'s own docstring
    (services/leads/intelligence.py) for exactly which one each field
    reuses. next_action/execution_blocked are read from
    compute_global_decision()'s own decision dict, the same one GET
    /workday/enforcement-state's required_action/blocked are built from —
    guaranteed to never disagree (Task 5)."""

    revenue_today_expected: int
    revenue_today_gap: float
    revenue_at_risk: int
    biggest_opportunity: BiggestOpportunity | None = None
    next_action: str
    execution_blocked: bool
