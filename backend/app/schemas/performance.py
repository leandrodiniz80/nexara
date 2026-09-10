from pydantic import BaseModel, Field


class UserPerformanceResponse(BaseModel):
    """compute_user_performance() (team_performance.py) — one entry per
    team member. user_id/name are both just the raw owner_email string:
    this codebase's real user identity is platform_users.email (a primary
    key, not a surrogate id), and PlatformUser carries no display-name
    column at all (see that model's own docstring) — there is nothing else
    to put in either field. "Team member" means anyone who owns at least
    one lead in this org (Lead.owner_email), not every PlatformUser row —
    a revenue leaderboard is about who's actually working leads, not org
    membership in the abstract.

    revenue_converted sums estimated_value (raw, unweighted) across this
    user's own converted leads; revenue_at_risk sums expected_value
    (probability-weighted) across their high/critical deal_risk_level
    leads — both reuse whatever compute_user_performance()'s own
    score_leads() pass already computed, no extra per-user query.
    response_rate/avg_response_time_minutes are all-time (not windowed),
    same "all time, no window" precedent compute_action_effectiveness()
    already sets, derived from LeadActivityLog rows this user themselves
    logged (message_sent they sent vs. response-type entries they
    recorded — see record_lead_response()'s own docstring, leads.py, for
    why a response event's user_email is the recording user, not
    necessarily who sent the original message: a disclosed approximation).
    actions_executed_today counts today's action_call/action_message/
    action_meeting/action_auto_message/action_auto_meeting entries
    attributed to this user. commission_estimate is 5% of
    revenue_converted. streak_days is consecutive days (ending today, or
    yesterday if today has none yet — same "doesn't drop at midnight"
    rule GET /workday/target's own streak already follows) with at least
    one "lead_won" entry this user logged.

    deals_closed (Ultimate-Sales-OS round, Task 11) is the count of this
    user's own converted leads — distinct from leads_handled, which counts
    every lead they own regardless of status. revenue_converted is the sum
    of value across the same set deals_closed counts.

    Revenue Per User real-time (Elite round, Task 5): revenue_today/
    revenue_this_week are the same estimated_value sum as revenue_converted
    (all-time), just windowed to conversions whose own "lead_won"
    LeadActivityLog entry landed today/within the last 7 days respectively
    — revenue_this_week always >= revenue_today, since today is inside this
    week's own window. pipeline_value is this user's own open (not
    converted/lost) leads' expected_value summed — the probability-weighted
    forecast still sitting in their pipeline, distinct from revenue_at_risk
    above (which only counts their high/critical-risk subset)."""

    user_id: str
    name: str
    leads_handled: int = 0
    deals_closed: int = 0
    revenue_converted: float = 0.0
    revenue_at_risk: int = 0
    revenue_today: float = 0.0
    revenue_this_week: float = 0.0
    pipeline_value: int = 0
    response_rate: float = 0.0
    avg_response_time_minutes: float | None = None
    actions_executed_today: int = 0
    commission_estimate: float = 0.0
    streak_days: int = 0
    badges: list[str] = Field(default_factory=list)


class LeaderboardEntry(BaseModel):
    """GET /performance/leaderboard's own per-row shape — the prompt's own
    literal field list (user_id/name/revenue_converted/response_rate/
    avg_response_time/position), plus commission_estimate/badges additive
    on top (Tasks 3/4's own "expose in leaderboard" instruction),
    deals_closed additive on top of that (Ultimate-Sales-OS round, Task
    11), and revenue_today/revenue_this_week/pipeline_value on top of that
    (Elite round, Task 5) — see UserPerformanceResponse's own docstring for
    what each means."""

    user_id: str
    name: str
    revenue_converted: float
    response_rate: float
    avg_response_time_minutes: float | None
    position: int
    commission_estimate: float = 0.0
    badges: list[str] = Field(default_factory=list)
    deals_closed: int = 0
    revenue_today: float = 0.0
    revenue_this_week: float = 0.0
    pipeline_value: int = 0


class TeamSummaryResponse(BaseModel):
    """GET /performance/team-summary — the org-wide roll-up of
    compute_user_performance()'s own per-user list. top_performer_name/
    worst_performer_name are the same #1/last entries
    rank_user_performance() (team_performance.py) would produce — both
    None only when the org has no team members with leads at all."""

    total_revenue: float = 0.0
    total_converted_today: int = 0
    total_at_risk: int = 0
    avg_response_rate: float = 0.0
    top_performer_name: str | None = None
    worst_performer_name: str | None = None


class PressureStateResponse(BaseModel):
    """GET /performance/pressure-state — the calling user's own Sales
    Pressure Engine classification (compute_user_pressure_state(),
    team_performance.py, final round): one of "leader"/"neutral"/
    "at_risk"/"underperforming". message is the same ready-to-render
    sentence maybe_notify_user_pressure()'s own notification would carry
    for that state — always populated (even for "neutral", where it's a
    plain, calm sentence) so the frontend's pressure banner never has to
    invent its own copy for the un-alerted case."""

    state: str
    message: str
