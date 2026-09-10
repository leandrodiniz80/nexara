from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.leads.lead import Lead
from app.models.leads.lead_activity_log import LeadActivityLog
from app.models.notifications.user_notification import UserNotification
from app.schemas.leads.lead import LeadResponse
from app.services.leads.enrichment import format_brl, generate_smart_message
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


async def _cadence_steps_done_by_lead(db: AsyncSession, lead_ids: list) -> dict:
    """Per-lead execution memory for the Smart Follow-up cadence (Task 3,
    final round) — LeadActivityLog IS the memory, no new column needed:
    auto_execute_engine() below only ever fires generate_follow_up_
    sequence()'s own steps (scoring.py) in order, one at a time per call,
    so the count of a lead's own action_auto_message/action_auto_meeting
    rows already logged doubles as exactly how many cadence steps have
    executed for it so far — a plain grouped count, one query regardless
    of batch size."""
    if not lead_ids:
        return {}
    stmt = (
        select(LeadActivityLog.lead_id, func.count(LeadActivityLog.id))
        .where(
            LeadActivityLog.lead_id.in_(lead_ids),
            LeadActivityLog.event_type.in_(list(AUTO_ACTION_EVENT_TYPE_BY_ACTION.values())),
        )
        .group_by(LeadActivityLog.lead_id)
    )
    return dict((await db.execute(stmt)).all())


def _next_due_cadence_action(response: LeadResponse, steps_done: int, now: datetime) -> str | None:
    """Full Autonomous Cadence Execution (Task 3, final round) — the next
    generate_follow_up_sequence() step (scoring.py) not yet executed for
    this lead, if its own day has arrived. "Arrived" (days_elapsed >=
    day_offset), not "exactly today" — a real upgrade over this
    function's own previous exact-day-only check, made safe now that
    steps_done (from _cadence_steps_done_by_lead() above) gives real
    per-lead memory instead of relying on "did today happen to match."
    None once every step in the sequence is already done, or the lead's
    own response state changed the sequence out from under an
    in-progress index (steps_done >= len(sequence) covers both). Never
    returns "call_now" — the only two actions this can ever produce are
    send_message/schedule_meeting, the same hard "never auto-call"
    guarantee this function's caller already relies on."""
    sequence = follow_up_sequence_for_state(response.lead_response_state)
    if steps_done >= len(sequence):
        return None
    next_step = sequence[steps_done]
    if (now - response.created_at).days < next_step["day_offset"]:
        return None
    if next_step["action"] == "call_now":
        return None
    return next_step["action"]


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
      3. Full Autonomous Cadence Execution (Task 3, Adaptive Intelligence
         round; upgraded to the FULL sequence — message steps too, not
         just meetings — final round) — whenever generate_follow_up_
         sequence()'s own cadence (scoring.py) says this lead's next
         not-yet-executed step (per-lead memory: _cadence_steps_done_by_
         lead()'s own count of this lead's past action_auto_* rows) has
         reached its own day, independent of win_probability entirely.
         A cadence-due send_message step gets a message generated on the
         spot via generate_smart_message() (enrichment.py) when the
         existing next-best-action pipeline hadn't already populated
         ready_to_send_message for other reasons. Still excludes
         "critical" risk, same rationale as rule 2. Stops naturally once
         the lead converts or is lost (both already excluded from this
         loop's own candidates above) or once every step in its own
         sequence has executed (_next_due_cadence_action() returns None).

    call_now is never auto-executed — no rule above ever produces it (rule
    3 in particular never even evaluates the cadence's own call_now step —
    see _next_due_cadence_action()'s own docstring for why that's
    structural, not just a filter this function applies on top).

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

    # Full Autonomous Cadence Execution (Task 3, final round) — one query
    # for the whole batch's own per-lead cadence progress, read once here
    # rather than per lead inside the loop below.
    cadence_steps_done = await _cadence_steps_done_by_lead(
        db, [response.id for response in leads]
    )

    candidates: list[tuple[LeadResponse, str]] = []
    # Cadence-triggered send_message candidates need a message generated
    # on the spot (the existing next-best-action pipeline hadn't already
    # populated ready_to_send_message for them) — tracked here so the
    # execution loop below knows which ones to generate for, once it has
    # the raw Lead row generate_smart_message() needs.
    needs_generated_message: set = set()
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
            continue
        if (
            response.deal_risk_level != "critical"
            and is_within_overdue_grace
            and response.win_probability >= _AUTO_EXECUTE_MEETING_WIN_PROBABILITY
        ):
            candidates.append((response, "schedule_meeting"))
            continue
        if response.deal_risk_level == "critical":
            continue

        # Full Autonomous Cadence Execution (Task 3, final round) —
        # replaces the previous exact-day, meetings-only cadence check
        # with the fuller generate_follow_up_sequence() progression (see
        # _next_due_cadence_action()'s own docstring): whichever step this
        # lead's own per-lead memory says is next, message or meeting,
        # once its day has arrived. Never call_now — structural, not a
        # filter this loop applies on top.
        cadence_action = _next_due_cadence_action(
            response, cadence_steps_done.get(response.id, 0), now
        )
        if cadence_action == "schedule_meeting":
            candidates.append((response, "schedule_meeting"))
        elif cadence_action == "send_message":
            candidates.append((response, "send_message"))
            needs_generated_message.add(response.id)

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

        if response.id in needs_generated_message:
            generated_message = generate_smart_message(
                lead,
                response.next_best_action,
                lead.owner_email or "the team",
                deal_risk_level=response.deal_risk_level,
                lead_response_state=response.lead_response_state,
                matches_top_combination=False,
            )
            if generated_message is None:
                continue
            response = response.model_copy(update={"ready_to_send_message": generated_message})

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
