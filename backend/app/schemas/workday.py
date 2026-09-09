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
