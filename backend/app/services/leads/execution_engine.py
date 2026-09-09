from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.leads.lead import Lead
from app.models.leads.lead_activity_log import LeadActivityLog
from app.models.notifications.user_notification import UserNotification
from app.schemas.leads.lead import LeadResponse
from app.services.leads.enrichment import format_brl

# maybe_auto_execute()'s own UserNotification message is matched back by
# this prefix wherever "how many auto-executions happened today" needs
# counting (GET /workday/summary's auto_actions_executed_today, .../
# performance's own copy) — same "structured info via string matching"
# technique LOSS_REASON_MARKER (scoring.py) already uses, since
# UserNotification has no discriminator column of its own (see that
# model's own docstring). Distinct from anything execute_lead_action()
# itself logs (a LeadActivityLog entry, not a UserNotification), so a
# manual "Enviar agora" click is never miscounted as an auto-execution.
AUTO_EXECUTION_NOTIFICATION_PREFIX = "Mensagem enviada automaticamente para salvar"


class InvalidLeadAction(ValueError):
    """Raised by execute_lead_action() when the requested action's own
    precondition isn't met (today, only send_message has one: a
    ready_to_send_message) or the action string itself is unrecognized.
    The router catches this and 400s."""


# Execution-engine round — a second LeadActivityLog entry per executed
# action, on top of (not instead of) the event-specific one the if/elif
# chain below already writes (message_sent/call_initiated/meeting_scheduled
# — kept as-is since message_sent in particular is read elsewhere for
# has_pending_response/response_delay_minutes, scoring.py). This one exists
# purely so compute_action_effectiveness() (scoring.py) has one uniform
# "an action of type X ran" marker to query across all three action types
# at once (event_type.in_([...]))  instead of three differently-named
# columns/values that don't share a common prefix it could match on.
ACTION_EFFECTIVENESS_EVENT_TYPE_BY_ACTION = {
    "call_now": "action_call",
    "send_message": "action_message",
    "schedule_meeting": "action_meeting",
}


async def execute_lead_action(
    db: AsyncSession,
    lead: Lead,
    action: str,
    *,
    response: LeadResponse,
    organization_id: str,
    user_email: str | None,
) -> None:
    """Execution-assistance round's action engine — the mutating half of
    the AI Deal Coach's action recommendation (compute_action_type_and_urgency,
    scoring.py). `response` is that same lead's own already-scored
    LeadResponse — POST /leads/{id}/execute-action scores the lead once
    before calling this (to validate the request and reuse
    suggested_message/ready_to_send_message rather than recomputing them
    here); this function only mutates `lead` and logs, it never re-scores
    or commits — same "caller commits" convention as complete_lead_task()
    (workday_engine.py).

    "last_activity_at" from this round's own spec doesn't exist as a
    column (Lead has no such field — see that model's own docstring); the
    closest existing equivalent is AuditMixin's updated_at, which normally
    bumps automatically via onupdate on any changed column but is set
    explicitly here so it bumps even on a no-op mutation (e.g. send_message
    on a lead that already had no next_action to clear)."""
    now = datetime.now(timezone.utc)

    if action == "send_message":
        if not response.ready_to_send_message:
            raise InvalidLeadAction("This lead has no ready-to-send message.")
        db.add(
            LeadActivityLog(
                organization_id=organization_id,
                lead_id=lead.id,
                lead_name=lead.name,
                event_type="message_sent",
                message="Mensagem enviada automaticamente",
                user_email=user_email,
            )
        )
        lead.next_action = None
        lead.next_action_due_at = None
    elif action == "call_now":
        db.add(
            LeadActivityLog(
                organization_id=organization_id,
                lead_id=lead.id,
                lead_name=lead.name,
                event_type="call_initiated",
                message="Ligação iniciada",
                user_email=user_email,
            )
        )
    elif action == "schedule_meeting":
        lead.next_action = "Reunião agendada"
        lead.next_action_due_at = now + timedelta(days=1)
        db.add(
            LeadActivityLog(
                organization_id=organization_id,
                lead_id=lead.id,
                lead_name=lead.name,
                event_type="meeting_scheduled",
                message="Reunião agendada",
                user_email=user_email,
            )
        )
    else:
        raise InvalidLeadAction(f"Unknown action: {action}")

    db.add(
        LeadActivityLog(
            organization_id=organization_id,
            lead_id=lead.id,
            lead_name=lead.name,
            event_type=ACTION_EFFECTIVENESS_EVENT_TYPE_BY_ACTION[action],
            message=f"Action executed: {action}",
            user_email=user_email,
        )
    )
    lead.updated_at = now


async def maybe_auto_execute(db: AsyncSession, lead: Lead, response: LeadResponse) -> bool:
    """Execution-assistance round's auto-execution layer — gated behind
    settings.AUTO_MODE_ENABLED (off by default). Per this round's own
    explicit safety mandate: NEVER auto-executes call_now or
    schedule_meeting, only send_message, and only when
    response.auto_action_available is already true (the same
    next_best_action_type == "send_message" AND suggested_message-exists
    gate LeadResponse itself computes) — deal_risk_level == "critical" is
    this function's own extra bar on top of that, so a routine send_message
    recommendation on a merely "medium"-risk lead is never auto-sent, only
    a lead about to be lost. Skips leads with no owner_email — nobody to
    attribute the resulting notification to (same constraint
    maybe_notify_high_value_leads/maybe_notify_critical_deals already
    apply, workday_engine.py). Caller commits; returns whether it actually
    executed."""
    if not settings.AUTO_MODE_ENABLED:
        return False
    if response.deal_risk_level != "critical" or not response.auto_action_available:
        return False
    if lead.owner_email is None:
        return False

    await execute_lead_action(
        db,
        lead,
        "send_message",
        response=response,
        organization_id=lead.organization_id,
        user_email=lead.owner_email,
    )
    db.add(
        UserNotification(
            organization_id=lead.organization_id,
            user_email=lead.owner_email,
            lead_id=lead.id,
            message=(
                f"{AUTO_EXECUTION_NOTIFICATION_PREFIX} um lead de "
                f"R$ {format_brl(response.expected_value)}."
            ),
        )
    )
    return True
