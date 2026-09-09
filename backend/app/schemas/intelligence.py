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
    combining today's lost opportunity with the Revenue Simulation
    Engine's own optimistic delta. Same "the backend writes the sentence"
    rule build_priority_reason()/focus_message/accountability_message
    already follow elsewhere in this codebase."""

    message: str
