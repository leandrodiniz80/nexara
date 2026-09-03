from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.leads.automation_activity_log import AutomationActivityLog
from app.models.leads.lead import Lead
from app.models.leads.lead_automation import LeadAutomation
from app.models.notifications.user_notification import UserNotification
from app.services.leads.enrichment import simulate_enrichment

logger = logging.getLogger("app.services.leads.automation_engine")

_DEFAULT_AUTOMATIONS = [
    {
        "name": "New → Contacted",
        "trigger_type": "lead_status_changed",
        "trigger_from": "new",
        "trigger_to": "contacted",
        "action_type": "notify",
        "active": True,
    },
    {
        "name": "Contacted → Converted",
        "trigger_type": "lead_status_changed",
        "trigger_from": "contacted",
        "trigger_to": "converted",
        "action_type": "log",
        "active": True,
    },
    {
        "name": "Lead Created Notification",
        "trigger_type": "lead_created",
        "trigger_from": None,
        "trigger_to": None,
        "action_type": "notify",
        "active": True,
    },
    {
        # No fromStatus/toStatus at all (unlike lead_status_changed) — this
        # trigger fires from a time-based condition (no update in N days),
        # evaluated inside GET /leads/attention, not a discrete transition.
        "name": "Stale Contacted Lead",
        "trigger_type": "lead_stale",
        "trigger_from": None,
        "trigger_to": None,
        "action_type": "notify",
        "active": True,
    },
    {
        # First operational (not just informative) action type: instead of
        # only logging/notifying, this one actually schedules a follow-up on
        # the lead itself. Fixed 1-day delay + fixed task text for now — no
        # LeadAutomation column exists to make either configurable per-row,
        # and none is worth adding for a single automation.
        "name": "Auto-schedule First Contact",
        "trigger_type": "lead_created",
        "trigger_from": None,
        "trigger_to": None,
        "action_type": "create_task",
        "active": True,
    },
    {
        # Same architecture as create_task — a lead starts building its
        # "mini-dossier" the moment it exists, no one has to remember to
        # click Enrich manually.
        "name": "Auto-enrich New Lead",
        "trigger_type": "lead_created",
        "trigger_from": None,
        "trigger_to": None,
        "action_type": "enrich",
        "active": True,
    },
]


class AutomationEvent(TypedDict, total=False):
    type: str
    lead: Lead
    fromStatus: str | None
    toStatus: str | None


async def seed_default_automations(db: AsyncSession, organization_id: str) -> None:
    """Inserts every default automation for an organization that doesn't
    already exist, by name — safe to call unconditionally on every
    GET /automations (not just for brand-new orgs): ON CONFLICT DO NOTHING
    against the (organization_id, name) unique constraint makes an existing
    row a no-op, so adding a new entry to _DEFAULT_AUTOMATIONS later (like
    "Lead Created Notification") automatically backfills it for orgs that
    already had the older two, without ever duplicating anything.
    """
    stmt = pg_insert(LeadAutomation).values(
        [{**automation, "organization_id": organization_id} for automation in _DEFAULT_AUTOMATIONS]
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=["organization_id", "name"])
    await db.execute(stmt)
    await db.commit()


async def run_automations(db: AsyncSession, event: AutomationEvent) -> list[str]:
    """Matches the event against every active LeadAutomation for the lead's
    organization. Partial trigger match: an automation with trigger_from/
    trigger_to left NULL matches any status on that side (always true for a
    "lead_created" event, which has no from/to status at all).

    Unrelated to app/automation/ (that package binds Workflows to Triggers —
    a different subsystem entirely; see LeadAutomation's own docstring).

    "log" writes to the server log via `logger.info()` — no UI concern, safe
    to do here. "notify" has no server-side channel to show a toast on, so
    its message is collected and returned instead; the route handler puts it
    on the HTTP response, and the frontend renders it as a toast from there.

    Every firing (both action types) is also staged as an AutomationActivityLog
    row via db.add() — not committed here, same as LeadStatusHistory below:
    the caller's single db.commit() (create_lead / update_lead_status) covers
    it atomically alongside the lead write.
    """
    from_status = event.get("fromStatus")
    to_status = event.get("toStatus")

    stmt = select(LeadAutomation).where(
        LeadAutomation.organization_id == event["lead"].organization_id,
        LeadAutomation.active.is_(True),
        LeadAutomation.trigger_type == event["type"],
    )
    result = await db.execute(stmt)
    automations = result.scalars().all()

    notifications: list[str] = []

    for automation in automations:
        if automation.trigger_from is not None and automation.trigger_from != from_status:
            continue
        if automation.trigger_to is not None and automation.trigger_to != to_status:
            continue

        if event["type"] == "lead_created":
            message = f"New lead created: {event['lead'].name}"
        elif event["type"] == "lead_stale":
            message = f"{event['lead'].name} has had no activity in a while — consider following up"
        else:
            message = f"Lead moved to {str(to_status).capitalize()}"

        if automation.action_type == "log":
            logger.info(
                "Automation triggered: %s (lead=%s, %s -> %s)",
                automation.name,
                event["lead"].id,
                from_status,
                to_status,
            )
        elif automation.action_type == "notify":
            notifications.append(message)
            logger.info(
                "Automation triggered: %s (lead=%s) -> notify %r",
                automation.name,
                event["lead"].id,
                message,
            )
            # Persistent counterpart to the toast above — only when the lead
            # has an owner: that's the one clear recipient this codebase can
            # derive without a "who triggered this" concept (lead_stale in
            # particular fires from a background sweep, no request/session
            # at all). An unowned lead still gets the toast, just no row
            # here — there's nobody specific to notify persistently.
            if event["lead"].owner_email:
                db.add(
                    UserNotification(
                        organization_id=event["lead"].organization_id,
                        user_email=event["lead"].owner_email,
                        lead_id=event["lead"].id,
                        message=message,
                    )
                )
        elif automation.action_type == "create_task":
            event["lead"].next_action = "Contact within 1 day"
            event["lead"].next_action_due_at = datetime.now(timezone.utc) + timedelta(days=1)
            logger.info(
                "Automation triggered: %s (lead=%s) -> create_task %r due %s",
                automation.name,
                event["lead"].id,
                event["lead"].next_action,
                event["lead"].next_action_due_at,
            )
        elif automation.action_type == "enrich":
            simulate_enrichment(event["lead"])
            logger.info(
                "Automation triggered: %s (lead=%s) -> enrich",
                automation.name,
                event["lead"].id,
            )
        else:
            continue

        db.add(
            AutomationActivityLog(
                organization_id=event["lead"].organization_id,
                lead_id=event["lead"].id,
                lead_name=event["lead"].name,
                automation_name=automation.name,
                action_type=automation.action_type,
                message=message,
            )
        )

    return notifications


async def fire_stale_lead_automations(
    db: AsyncSession, leads: list[Lead], cutoff: datetime
) -> int:
    """Fires "lead_stale" for every contacted lead in `leads` whose
    organization has an active lead_stale automation, deduped against
    AutomationActivityLog so calling this again inside the same staleness
    window (`cutoff`) never re-notifies the same lead. Shared by
    GET /leads/attention (opportunistic, one org at a time — whichever org
    the caller belongs to) and POST /internal/jobs/check-stale-leads (a
    cross-org sweep — the same logic, minus a single organization_id
    filter): identical semantics, one place, so the manual job endpoint
    today needs no rewrite once it becomes a real scheduled job later.
    Caller commits; this only stages writes via run_automations()'s own
    db.add() calls.
    """
    contacted = [lead for lead in leads if lead.status == "contacted"]
    if not contacted:
        return 0

    org_ids = {lead.organization_id for lead in contacted}
    triggers_stmt = select(LeadAutomation.organization_id, LeadAutomation.name).where(
        LeadAutomation.organization_id.in_(org_ids),
        LeadAutomation.active.is_(True),
        LeadAutomation.trigger_type == "lead_stale",
    )
    trigger_names_by_org: dict[str, list[str]] = {}
    for organization_id, name in (await db.execute(triggers_stmt)).all():
        trigger_names_by_org.setdefault(organization_id, []).append(name)

    fired = 0
    for lead in contacted:
        trigger_names = trigger_names_by_org.get(lead.organization_id)
        if not trigger_names:
            continue

        already_notified_stmt = (
            select(AutomationActivityLog.id)
            .where(
                AutomationActivityLog.lead_id == lead.id,
                AutomationActivityLog.automation_name.in_(trigger_names),
                AutomationActivityLog.created_at >= cutoff,
            )
            .limit(1)
        )
        if (await db.execute(already_notified_stmt)).first() is not None:
            continue

        await run_automations(db, {"type": "lead_stale", "lead": lead})
        fired += 1

    return fired
