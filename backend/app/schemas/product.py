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


class ProductIdentity(BaseModel):
    """compute_product_identity()'s own output (Task 1, revenue-operating-
    system round) — how this product is positioned for this tenant."""

    product_category: str
    primary_value: str
    target_market: str
    sales_complexity: str


class RoiEstimate(BaseModel):
    """compute_roi_estimate()'s own output (Task 2, revenue-operating-
    system round) — the monthly/annual recoverable upside a sales
    conversation leads with."""

    estimated_monthly_revenue_gain: float
    estimated_annual_revenue_gain: float
    roi_multiple: float


class PricingSuggestion(BaseModel):
    """compute_pricing_suggestion()'s own output (Task 3, revenue-
    operating-system round)."""

    recommended_plan: str
    monthly_price: float
    setup_price: float
    pricing_logic: str


class ObjectionHandler(BaseModel):
    """One entry of generate_objection_handlers()'s own fixed list (Task
    5, revenue-operating-system round)."""

    objection: str
    answer: str


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

    # Revenue Command Center (revenue-command-center round) — additive.
    # revenue_gap is the floored-at-zero, pressure-facing sibling of
    # revenue_today_gap (see compute_revenue_gap()'s own docstring,
    # services/leads/intelligence.py); decision_score quantifies urgency
    # independently of sales_readiness_score; required_actions_today/
    # required_calls_today/required_messages_today are compute_required_
    # actions()'s own daily quota; pressure_message is the one sentence
    # engineered to be impossible to ignore.
    revenue_gap: float
    decision_score: int
    required_actions_today: int
    required_calls_today: int
    required_messages_today: int
    pressure_message: str

    # Self-Optimizing Revenue Brain (self-optimizing-revenue-brain round)
    # — additive. efficiency_mode/next_best_move are compute_efficiency_
    # mode()/compute_next_best_move()'s own output; system_health/
    # system_status are compute_system_health()'s own health_score/status
    # (renamed at this level so they don't collide with the product-layer
    # round's own system_state object above); failure_pattern_detected is
    # true when compute_failure_patterns() found a real top_loss_reason or
    # worst_channel signal in the org's own recent outcomes. See
    # services/leads/intelligence.py for all of the above.
    efficiency_mode: str
    next_best_move: str
    system_health: int
    system_status: str
    failure_pattern_detected: bool

    # Revenue Operating System (revenue-operating-system round) —
    # additive, go-to-market layer. See services/leads/intelligence.py
    # for compute_product_identity()/compute_roi_estimate()/
    # compute_pricing_suggestion()/generate_sales_script()/
    # generate_objection_handlers().
    product_identity: ProductIdentity
    roi_estimate: RoiEstimate
    pricing_suggestion: PricingSuggestion
    sales_script: str
    objection_handlers: list[ObjectionHandler]
