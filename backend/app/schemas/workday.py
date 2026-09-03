from pydantic import BaseModel

from app.schemas.leads.lead import LeadResponse


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
