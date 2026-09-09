import uuid
from typing import Literal

from pydantic import BaseModel

from app.schemas.leads.lead import LeadResponse

FailureState = Literal["on_track", "at_risk", "failing"]


class WorkdayNextResponse(BaseModel):
    """GET /workday/next. lead is None only when there's nothing left to
    work on (empty queue) — the frontend shows a "caught up" state instead
    of opening a modal. is_new_focus distinguishes a freshly-picked lead
    from an idempotent re-return of whichever lead the caller already had
    in focus (calling this endpoint again mid-session never advances past
    an unfinished lead — see get_workday_next()'s own docstring)."""

    lead: LeadResponse | None
    is_new_focus: bool
    tasks_completed_today: int
    streak_days: int


class WorkdaySummaryResponse(BaseModel):
    """GET /workday/summary — the "what does today look like" snapshot the
    Command Center reads on load. focus_message is a ready-to-render
    sentence built server-side (_build_focus_message() in workday.py), same
    "backend writes the sentence" rule the timeline/activity feed already
    follow."""

    today_tasks: int
    overdue_tasks: int
    high_priority_leads: int
    leads_at_risk: int
    estimated_revenue_at_risk: float
    focus_message: str
    # Revenue-intelligence round, both additive. revenue_at_risk is a
    # narrower, probability-weighted figure than estimated_revenue_at_risk
    # above: contacted leads that are overdue OR stale (vs. that field's
    # contacted+stale-only), summed by expected_value (vs. raw estimated
    # value) — "money genuinely at risk, probability-adjusted" rather than
    # "money attached to leads going cold." today_potential_revenue is the
    # Command Center's "Hoje você pode gerar R$ X": expected_value summed
    # over today's actionable leads (overdue + due today).
    revenue_at_risk: int = 0
    today_potential_revenue: int = 0
    # AI Deal Coach round, all additive/derived at read time from the same
    # already-scored `ranked` list this endpoint already computes — zero new
    # queries. money_in_play_today is the same figure as
    # today_potential_revenue above, just re-exposed under the Deal Coach's
    # own vocabulary (expected_value summed over today's actionable leads);
    # money_at_risk_today narrows that further to only deal_risk_level ==
    # "critical" leads (compute_deal_risk, scoring.py); critical_deals_count
    # is how many of those there are.
    money_in_play_today: int = 0
    money_at_risk_today: int = 0
    critical_deals_count: int = 0


class WorkdayCompleteAndNextRequest(BaseModel):
    lead_id: uuid.UUID


class WorkdayCompleteAndNextResponse(BaseModel):
    """POST /workday/complete-and-next. next_lead is None once the queue is
    empty — same "caught up" signal as WorkdayNextResponse.lead — so the
    frontend can end the flow instead of trying to open a null lead.
    completed_lead carries the just-completed lead's fresh state (cleared
    next_action, updated score) alongside completed_lead_id, so the
    frontend can patch its local caches the same way POST
    /leads/{id}/complete-task's response already lets it."""

    completed_lead_id: uuid.UUID
    completed_lead: LeadResponse
    next_lead: LeadResponse | None


class WorkdayPerformanceResponse(BaseModel):
    """GET /workday/performance — the accountability layer's own snapshot:
    how much of today's expected work actually got done, what yesterday's
    neglect is now costing, and the streak. failure_state/
    accountability_message are additive beyond the original spec's literal
    field list — the Performance Panel needs both to render its message and
    color, and there's no other endpoint that already carries them."""

    tasks_completed_today: int
    tasks_expected_today: int
    completion_rate: float
    overdue_tasks: int
    leads_ignored_yesterday: int
    estimated_revenue_lost: float
    streak_days: int
    failure_state: FailureState
    accountability_message: str
    # Same probability-weighted "contacted + (overdue or stale)" figure as
    # WorkdaySummaryResponse.revenue_at_risk above — additive.
    revenue_at_risk: int = 0
    # AI Deal Coach round. critical_deals is the same deal_risk_level ==
    # "critical" count as WorkdaySummaryResponse.critical_deals_count, reused
    # from this endpoint's own already-computed `ranked` list. money_saved_today
    # is a proxy, not an exact figure: the exact deal_risk_level a now-
    # completed lead had *before* its task was finished isn't recoverable at
    # read time (completing it clears next_action_due_at/bumps updated_at, so
    # recomputing risk now would show "low") — so this sums estimated_value
    # for leads with a task_completed activity today whose estimated_value
    # clears HIGH_VALUE_LEAD_THRESHOLD, as a stand-in for "high-value deals
    # that got acted on today instead of going cold."
    critical_deals: int = 0
    money_saved_today: float = 0


class WorkdayTargetResponse(BaseModel):
    """GET /workday/target — the daily gamification target. daily_target is
    a fixed default for now (no per-user/org customization yet); completed_
    today reuses the same tasks_completed_today _workday_stats() already
    computes for GET /workday/next and .../performance."""

    daily_target: int
    completed_today: int
    remaining: int
    progress: float
