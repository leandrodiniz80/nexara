from pydantic import BaseModel


class RevenueSimulationResponse(BaseModel):
    """GET /intelligence/revenue-simulation — simulate_revenue_if_all_
    actions_executed()'s own {current_expected, optimized_expected, delta}
    shape (scoring.py), typed for the API contract. current_expected is
    the same win_probability-weighted sum score_leads() already exposes
    per lead (LeadResponse.expected_value); optimized_expected assumes
    every pending action gets executed and every open lead's own
    win_probability is boosted accordingly — see that function's own
    docstring for the exact, disclosed assumption. delta is always
    optimized_expected - current_expected."""

    current_expected: int = 0
    optimized_expected: int = 0
    delta: int = 0


class ExecInsightResponse(BaseModel):
    """GET /intelligence/exec-insight — generate_exec_insight()'s own
    ready-to-render sentence (app/services/leads/intelligence.py),
    combining today's lost opportunity, the Revenue Simulation Engine's
    own optimistic delta, the current aggression level, the global
    strategy's focus, and any revenue leak count (final round). Same "the
    backend writes the sentence" rule build_priority_reason()/
    focus_message/accountability_message already follow elsewhere in this
    codebase."""

    message: str


class GlobalStrategyResponse(BaseModel):
    """GET /intelligence/global-strategy — compute_global_strategy()'s own
    {focus, reason, confidence} shape (scoring.py), typed for the API
    contract. focus is always one of "calls"/"messages"/"meetings";
    confidence is 0-100, not a probability in the statistical sense — a
    plain "how strong is this rule's own signal" indicator."""

    focus: str
    reason: str
    confidence: int = 0


class AggressionLevelResponse(BaseModel):
    """GET /intelligence/aggression-level — compute_aggression_level()'s
    own return value (scoring.py), one of "low"/"medium"/"high"/
    "extreme". revenue_mode (final round) is compute_revenue_mode()'s own
    one-line relabeling of that same level into "efficiency"/"balanced"/
    "aggressive" — the vocabulary this round's own Command Center
    indicator asks for, same underlying signal as `level`, not a second
    computation (see that function's own docstring)."""

    level: str
    revenue_mode: str = "balanced"


class RevenueLeaksResponse(BaseModel):
    """GET /intelligence/revenue-leaks — detect_revenue_leaks()'s own
    shape (scoring.py): three independent leak-pattern counts plus
    total_leak_value, the summed expected_value across every lead caught
    by at least one of the three patterns (no double-counting a lead
    caught by more than one)."""

    leads_ignored_over_24h: int = 0
    high_value_leads_without_action: int = 0
    leads_stuck_same_stage: int = 0
    total_leak_value: int = 0
