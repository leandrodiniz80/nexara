from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.leads.lead import Lead
from app.models.leads.lead_activity_log import LeadActivityLog
from app.schemas.leads.lead import LeadResponse
from app.services.leads.scoring import rank_leads_by_priority


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
