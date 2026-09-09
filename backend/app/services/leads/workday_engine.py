from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.leads.lead import Lead
from app.models.leads.lead_activity_log import LeadActivityLog
from app.models.notifications.user_notification import UserNotification
from app.schemas.leads.lead import LeadResponse
from app.schemas.workday import FailureState
from app.services.leads.scoring import rank_leads_by_priority

# detect_user_failure_state()'s thresholds — see its own docstring.
_FAILING_COMPLETION_RATE = 0.3
_AT_RISK_COMPLETION_RATE = 0.6
_FAILING_OVERDUE_THRESHOLD = 5

# maybe_notify_performance_alert()'s dedup window — a "failing" alert isn't
# repeated more often than this, however often the dashboard is refreshed.
_PERFORMANCE_ALERT_DEDUP_HOURS = 6


async def get_next_actionable_lead(
    db: AsyncSession, organization_id: str, *, exclude_lead_id: uuid.UUID | None = None
) -> LeadResponse | None:
    """One lead to work on next for POST /workday/complete-and-next — same
    ranking rank_leads_by_priority() already gives GET /leads/priority
    (overdue first, then due today, then future, then no next_action at
    all; score DESC within each bucket), which already implies this
    endpoint's own stated criteria: an overdue or due-today lead always
    outranks everything else, and among leads with no due date at all the
    highest-scoring (most valuable, most worth not losing) one comes first.

    exclude_lead_id skips the lead the caller just completed — it usually
    wouldn't resurface anyway (its next_action is now cleared, so it's
    already fallen to the last bucket), but a small org with few other
    leads could otherwise hand the same lead right back."""
    ranked = await rank_leads_by_priority(db, organization_id)
    for response in ranked:
        if exclude_lead_id is not None and response.id == exclude_lead_id:
            continue
        return response
    return None


async def complete_lead_task(
    db: AsyncSession, lead: Lead, *, organization_id: str, user_email: str | None
) -> bool:
    """Shared body of POST /leads/{id}/complete-task and POST
    /workday/complete-and-next: logs the completion to LeadActivityLog
    (captured before clearing, so the timeline still shows what was done),
    clears next_action/next_action_due_at, and ends the caller's in-focus
    session on this lead if they hold one — identical behavior to the
    existing endpoint, just factored out so the new workday loop doesn't
    duplicate it. Returns False (nothing to do, caller should 400) when the
    lead has no next_action to complete; True otherwise. Caller commits."""
    if lead.next_action is None:
        return False

    now = datetime.now(timezone.utc)
    duration_seconds = None
    if lead.in_focus and lead.focused_by_email == user_email and lead.focused_at is not None:
        duration_seconds = int((now - lead.focused_at).total_seconds())
        lead.in_focus = False
        lead.focused_at = None
        lead.focused_by_email = None

    db.add(
        LeadActivityLog(
            organization_id=organization_id,
            lead_id=lead.id,
            lead_name=lead.name,
            event_type="task_completed",
            message=f"Task completed: {lead.next_action}",
            user_email=user_email,
            duration_seconds=duration_seconds,
        )
    )
    lead.next_action = None
    lead.next_action_due_at = None
    return True


def format_brl(value: float) -> str:
    """1234567.0 -> '1.234.567' — pt-BR thousands separator, no decimals
    (this is a rough estimate, not exact currency). Shared by
    _build_focus_message (workday.py) and generate_accountability_message
    below, so the two money-mentioning sentences format it identically."""
    return f"{value:,.0f}".replace(",", ".")


def detect_user_failure_state(*, completion_rate: float, overdue_tasks: int) -> FailureState:
    """"on_track" / "at_risk" / "failing" — a plain rule table over GET
    /workday/performance's own completion_rate/overdue_tasks, no ML.
    completion_rate can run above 1.0 (someone can complete more today than
    was strictly due today) — that still reads as on_track, which is
    correct."""
    if completion_rate < _FAILING_COMPLETION_RATE or overdue_tasks > _FAILING_OVERDUE_THRESHOLD:
        return "failing"
    if completion_rate < _AT_RISK_COMPLETION_RATE:
        return "at_risk"
    return "on_track"


def generate_accountability_message(
    *,
    failure_state: FailureState,
    overdue_tasks: int,
    leads_ignored_yesterday: int,
    estimated_revenue_lost: float,
    tasks_remaining_today: int,
) -> str:
    """The Performance Panel's (and Command Center's) headline sentence for
    the caller's current failure_state — built here, not the frontend, same
    "backend writes the sentence" rule the timeline/activity feed and
    _build_focus_message already follow. Leads with the financial framing
    (leads_ignored_yesterday and estimated_revenue_lost both > 0 — a lead
    only contributes revenue once it's been enriched, see
    get_lead_estimated_value()) whenever there's a real number to show;
    falls back to a plain activity-count message otherwise, in both
    failing and at_risk."""
    has_revenue_impact = leads_ignored_yesterday > 0 and estimated_revenue_lost > 0

    if failure_state == "failing":
        if has_revenue_impact:
            return (
                f"Você ignorou {leads_ignored_yesterday} leads que podem gerar "
                f"R$ {format_brl(estimated_revenue_lost)}. Aja agora antes que vire prejuízo real."
            )
        return f"Você está atrasado em {overdue_tasks} leads. Aja agora antes que piore."
    if failure_state == "at_risk":
        focus_count = max(tasks_remaining_today, 1)
        if has_revenue_impact:
            return (
                f"Você ainda pode recuperar seu dia. Foque nos próximos {focus_count} leads "
                f"antes de perder R$ {format_brl(estimated_revenue_lost)}."
            )
        return f"Você ainda pode recuperar seu dia. Foque nos próximos {focus_count} leads."
    return "Bom ritmo. Continue assim para fechar mais negócios hoje."


async def maybe_notify_performance_alert(
    db: AsyncSession, *, organization_id: str, user_email: str, message: str, now: datetime
) -> bool:
    """Persists a "failing"-state alert to UserNotification (so it also
    shows in the notification bell, same channel automation "notify"
    actions already use) — but only if the caller isn't due for a repeat
    yet. Deduped on lead_id IS NULL within _PERFORMANCE_ALERT_DEDUP_HOURS:
    every other notification kind always carries a lead_id (see
    automation_engine.py's own notify path, which only persists a row when
    the lead has an owner), so a null lead_id row is unambiguously one of
    these performance alerts. Caller commits; returns whether a row was
    actually staged."""
    cutoff = now - timedelta(hours=_PERFORMANCE_ALERT_DEDUP_HOURS)
    recent_alert_stmt = select(UserNotification.id).where(
        UserNotification.organization_id == organization_id,
        UserNotification.user_email == user_email,
        UserNotification.lead_id.is_(None),
        UserNotification.created_at >= cutoff,
    )
    already_sent = (await db.execute(recent_alert_stmt)).scalar_one_or_none()
    if already_sent is not None:
        return False

    db.add(
        UserNotification(
            organization_id=organization_id,
            user_email=user_email,
            lead_id=None,
            message=message,
        )
    )
    return True
