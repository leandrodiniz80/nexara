from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.leads.lead import Lead
from app.models.leads.lead_activity_log import LeadActivityLog
from app.models.notifications.user_notification import UserNotification
from app.schemas.leads.lead import LeadResponse
from app.services.leads.enrichment import format_brl
from app.services.leads.scoring import follow_up_sequence_for_state, update_adaptive_weights_realtime

# The execution-assistance round's own UserNotification message prefix —
# kept (not removed) purely so historical rows already written under it
# still count toward GET /workday/summary's auto_actions_executed_today
# (see that field's own _count_auto_actions_today, workday.py, which now
# matches either this or AUTO_EXECUTED_NOTIFICATION_PREFIX below). Nothing
# produces this prefix anymore as of the Autonomous-sales-OS round —
# auto_execute_engine() below (which replaced maybe_auto_execute(), this
# constant's original producer) writes AUTO_EXECUTED_NOTIFICATION_PREFIX
# instead.
AUTO_EXECUTION_NOTIFICATION_PREFIX = "Mensagem enviada automaticamente para salvar"
# Autonomous-sales-OS round — auto_execute_engine()'s own notification
# prefix (its literal ask: "message prefix = AUTO_EXECUTED:"), matched back
# the same way AUTO_EXECUTION_NOTIFICATION_PREFIX above already was.
AUTO_EXECUTED_NOTIFICATION_PREFIX = "AUTO_EXECUTED:"


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
        # Real-Time Learning Engine (Task 1, final round) — the one place
        # both manual (POST /leads/{id}/execute-action) and automated
        # (auto_execute_engine()) message_sent writes go through, so this
        # covers both without a second hook. Synchronous, in-memory.
        update_adaptive_weights_realtime({"type": "message_sent", "organization_id": organization_id})
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


# Autonomous-sales-OS round — auto_execute_engine()'s own hard daily
# ceiling (the prompt's own number), same "small, bounded" spirit as every
# other automation in this codebase that's gated behind a cap or dedup
# window rather than left to run unbounded.
_AUTO_EXECUTE_DAILY_LIMIT = 10
# auto_execute_engine()'s schedule_meeting rule — the prompt's own bar: a
# lead this likely to close, not already overdue, is safe to auto-book a
# meeting for. Kept as its own literal rather than importing
# scoring.py's _ATTEMPT_CLOSE_WIN_PROBABILITY (also 80): that one drives a
# display sentence, this one gates a real mutation, and the two shouldn't
# silently move together just because they happen to share a number today.
_AUTO_EXECUTE_MEETING_WIN_PROBABILITY = 80
# Revenue Acceleration Mode's own relaxation of the overdue check above
# (Task 3, revenue-maximization round) — "allow schedule_meeting even if
# slightly overdue," bounded to a small grace window rather than dropping
# the overdue check entirely: unbounded tolerance would contradict this
# codebase's own "safe, bounded automation" precedent every other auto-
# execution rule already follows.
_ACCELERATION_MEETING_OVERDUE_GRACE_DAYS = 1
# Ultimate-Sales-OS round (Task 6) — a second, higher bar that drops the
# grace-window bound entirely: a deal this likely to close (>= 85, above
# the plain _AUTO_EXECUTE_MEETING_WIN_PROBABILITY bar of 80) is safe to
# auto-book a meeting for no matter how overdue it's gotten, while
# acceleration mode is active. Still excludes "critical" risk the same way
# the grace-window rule above does (see auto_execute_engine()'s own
# candidate loop) — an emergency escalation still outranks a quietly
# auto-scheduled meeting.
_ACCELERATION_MEETING_HIGH_PROBABILITY = 85

# auto_execute_engine()'s own event-type vocabulary — an ADDITIONAL marker
# on top of (not a replacement for) whatever execute_lead_action() below
# already writes for the same call (its own message_sent/meeting_scheduled
# entry, plus the action_message/action_meeting one
# compute_action_effectiveness()/compute_revenue_attribution() read,
# scoring.py). This one exists purely so auto_execute_engine() itself has
# a per-lead idempotency check ("has this lead already been auto-executed
# today") and a daily count, both scoped to auto-executions specifically —
# neither of those existing markers distinguish an auto-execution from a
# manual "Enviar agora" click.
AUTO_ACTION_EVENT_TYPE_BY_ACTION = {
    "send_message": "action_auto_message",
    "schedule_meeting": "action_auto_meeting",
}


def _due_cadence_meeting(response: LeadResponse, now: datetime) -> bool:
    """Autonomous Cadence Execution (Task 3, Adaptive Intelligence round)
    — true when generate_follow_up_sequence()'s own cadence table
    (follow_up_sequence_for_state(), scoring.py) has a schedule_meeting
    step due *exactly* today, using response.created_at as the same
    day-0 anchor that function's own docstring establishes (no separate
    "sequence started" column exists). "Exactly," not "on or after": a
    dashboard visit on any other day simply misses that one step — same
    "close enough to act on" bar every other cheap approximation in this
    codebase already accepts, rather than firing the same step again on
    every later visit. Never returns true for call_now — the cadence
    table's own call_now step is structurally excluded here (this function
    only ever checks for "schedule_meeting"), so this can't be used to
    accidentally auto-call regardless of how it's wired up."""
    days_elapsed = (now - response.created_at).days
    return any(
        step["day_offset"] == days_elapsed and step["action"] == "schedule_meeting"
        for step in follow_up_sequence_for_state(response.lead_response_state)
    )


async def auto_execute_engine(
    db: AsyncSession, organization_id: str, leads: list[LeadResponse]
) -> int:
    """Autonomous-sales-OS round's real autopilot — upgrades the
    execution-assistance round's maybe_auto_execute() (critical-risk,
    send_message-only) into two independent, wider auto-execution rules,
    run inside GET /workday/summary over that same already-scored `leads`
    list (typically rank_leads_by_priority()'s own result — zero new
    candidate query):

      1. send_message whenever ready_to_send_message is populated — no
         risk-level qualifier this round (a structural guarantee, not a
         relaxed check: a critical-risk lead's own next_best_action_type
         is always forced to "call_now" by compute_action_type_and_urgency,
         scoring.py, so ready_to_send_message can never be set on one in
         the first place — auto-sending a critical lead's message was
         never actually possible to begin with, before or after this
         round).
      2. schedule_meeting whenever win_probability >=
         _AUTO_EXECUTE_MEETING_WIN_PROBABILITY AND the lead isn't
         overdue — a strong, unhurried deal safe to auto-book — EXCEPT
         deal_risk_level == "critical" leads even if they'd otherwise
         qualify (unlike rule 1, this one has no structural guarantee
         against it: a lead can be "critical" via the idle-days path
         without being overdue, and win_probability >= 80 doesn't
         preclude that). A critical lead needs the forced call_now
         escalation, never a quietly auto-scheduled meeting instead.
         Revenue Acceleration Mode (Task 3, revenue-maximization round)
         relaxes the "not overdue" half of this rule to "not overdue by
         more than _ACCELERATION_MEETING_OVERDUE_GRACE_DAYS" whenever
         response.acceleration_mode is true — LeadResponse's own global
         flag (see that field's own docstring, schemas/leads/lead.py),
         read straight from the already-scored `leads` list rather than a
         second DB round-trip. Ultimate-Sales-OS round (Task 6) adds a
         further relaxation on top: whenever acceleration_mode is true AND
         win_probability >= _ACCELERATION_MEETING_HIGH_PROBABILITY (85),
         the overdue check is skipped entirely (no grace-window bound at
         all) — a deal this close to closing gets its meeting booked
         regardless of how overdue it's become, while the org is behind
         target.
      3. Autonomous Cadence Execution (Task 3, Adaptive Intelligence
         round) — schedule_meeting again, independent of win_probability
         entirely this time: whenever generate_follow_up_sequence()'s own
         cadence (scoring.py) has a meeting step due *exactly* today (see
         _due_cadence_meeting()'s own docstring), regardless of how likely
         the lead looks. Still excludes "critical" risk, same rationale as
         rule 2.

    call_now is never auto-executed — no rule above ever produces it (rule
    3 in particular never even evaluates the cadence's own call_now step —
    see _due_cadence_meeting()'s own docstring for why that's structural,
    not just a filter this function applies on top).

    Gated behind settings.AUTO_MODE_ENABLED, same as the function this
    upgrades (off by default — a no-op, zero extra queries, until an org
    opts in). Bounded to _AUTO_EXECUTE_DAILY_LIMIT total executions per UTC
    day org-wide, counted via LeadActivityLog's own action_auto_message/
    action_auto_meeting rows (AUTO_ACTION_EVENT_TYPE_BY_ACTION) rather than
    UserNotification, so the cap holds even if a notification write ever
    failed independently. Idempotent per lead: the same query also
    excludes any lead already auto-executed today, so a dashboard refreshed
    several times in one day never re-executes the same lead. Requires
    owner_email (nobody to attribute the mutation/notification to
    otherwise — same constraint every other per-lead automation in this
    codebase already applies) and excludes converted/lost leads. Caller
    commits; returns how many were actually auto-executed this call (add
    to whatever the caller already had — same convention as the
    maybe_notify_* functions' own int returns, workday_engine.py)."""
    if not settings.AUTO_MODE_ENABLED:
        return 0

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    already_today_stmt = select(LeadActivityLog.lead_id).where(
        LeadActivityLog.organization_id == organization_id,
        LeadActivityLog.event_type.in_(list(AUTO_ACTION_EVENT_TYPE_BY_ACTION.values())),
        LeadActivityLog.created_at >= today_start,
    )
    already_today_ids = (await db.execute(already_today_stmt)).scalars().all()
    remaining = _AUTO_EXECUTE_DAILY_LIMIT - len(already_today_ids)
    if remaining <= 0:
        return 0
    already_executed_lead_ids = set(already_today_ids)

    candidates: list[tuple[LeadResponse, str]] = []
    for response in leads:
        if response.status in ("converted", "lost"):
            continue
        if response.owner_email is None:
            continue
        if response.id in already_executed_lead_ids:
            continue

        is_within_overdue_grace = (
            not response.is_overdue
            or (
                response.acceleration_mode
                and response.days_overdue is not None
                and response.days_overdue <= _ACCELERATION_MEETING_OVERDUE_GRACE_DAYS
            )
            or (
                response.acceleration_mode
                and response.win_probability >= _ACCELERATION_MEETING_HIGH_PROBABILITY
            )
        )

        if response.ready_to_send_message is not None:
            candidates.append((response, "send_message"))
        elif (
            response.deal_risk_level != "critical"
            and is_within_overdue_grace
            and response.win_probability >= _AUTO_EXECUTE_MEETING_WIN_PROBABILITY
        ):
            candidates.append((response, "schedule_meeting"))
        # Autonomous Cadence Execution (Task 3, Adaptive Intelligence
        # round) — a second, independent trigger for schedule_meeting:
        # generate_follow_up_sequence()'s own cadence (scoring.py) says a
        # meeting is due *exactly* today, regardless of win_probability.
        # Never call_now — see _due_cadence_meeting()'s own docstring for
        # why that's a structural guarantee here, not just a filter.
        elif response.deal_risk_level != "critical" and _due_cadence_meeting(response, now):
            candidates.append((response, "schedule_meeting"))

    if not candidates:
        return 0

    lead_ids = [response.id for response, _action in candidates]
    leads_stmt = select(Lead).where(Lead.id.in_(lead_ids))
    leads_by_id = {lead.id: lead for lead in (await db.execute(leads_stmt)).scalars().all()}

    executed = 0
    for response, action in candidates:
        if executed >= remaining:
            break
        lead = leads_by_id.get(response.id)
        if lead is None:
            continue

        await execute_lead_action(
            db,
            lead,
            action,
            response=response,
            organization_id=organization_id,
            user_email=lead.owner_email,
        )
        db.add(
            LeadActivityLog(
                organization_id=organization_id,
                lead_id=lead.id,
                lead_name=lead.name,
                event_type=AUTO_ACTION_EVENT_TYPE_BY_ACTION[action],
                message=f"Auto-executado: {action}",
                user_email=lead.owner_email,
            )
        )
        db.add(
            UserNotification(
                organization_id=organization_id,
                user_email=lead.owner_email,
                lead_id=lead.id,
                message=(
                    f"{AUTO_EXECUTED_NOTIFICATION_PREFIX} {action} para {lead.name} "
                    f"(R$ {format_brl(response.expected_value)})."
                ),
            )
        )
        executed += 1

    return executed
