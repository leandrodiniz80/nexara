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


class DynamicKpis(BaseModel):
    """compute_dynamic_kpis()'s own output (Task 2, product-layer round) —
    the response-time/actions-per-day/focus targets this tenant's own
    product_mode implies. See that function's own docstring
    (services/leads/intelligence.py)."""

    daily_target_revenue: float
    ideal_response_time_minutes: int
    ideal_actions_per_day: int
    focus_metric: str


class SystemState(BaseModel):
    """simplify_system_state()'s own output (Task 6, product-layer round)
    — the one status/sentence a non-technical owner needs, banded off
    sales_readiness_score."""

    status: str
    message: str


class ProductSummaryResponse(BaseModel):
    """GET /product/summary — the Revenue Decision System's single "explain
    it in seconds" view (Task 2/3, product-consolidation round; extended
    with the product layer — Tasks 1-6, product-layer round). Every field
    here is pure aggregation of a figure some other endpoint already
    computes — see compute_product_summary()'s own docstring
    (services/leads/intelligence.py) for exactly which one each field
    reuses. next_action/execution_blocked are read from
    compute_global_decision()'s own decision dict, the same one GET
    /workday/enforcement-state's required_action/blocked are built from —
    guaranteed to never disagree (Task 5, product-consolidation round).

    revenue_today_possible/next_best_action/top_priority_lead_id (product-
    layer round) are additive aliases for revenue_today_expected/
    next_action/biggest_opportunity.lead_id under this round's own literal
    field names — same values, not a second calculation, kept alongside
    the original names so nothing that already reads those breaks."""

    revenue_today_expected: int
    revenue_today_gap: float
    revenue_at_risk: int
    biggest_opportunity: BiggestOpportunity | None = None
    next_action: str
    execution_blocked: bool

    # Product layer (Tasks 1-6, product-layer round) — additive.
    product_mode: str
    sales_readiness_score: int
    main_action: str
    kpis: DynamicKpis
    system_state: SystemState
    revenue_today_possible: int
    next_best_action: str
    top_priority_lead_id: uuid.UUID | None = None
