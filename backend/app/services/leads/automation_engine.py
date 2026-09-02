from __future__ import annotations

import logging
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.leads.automation_activity_log import AutomationActivityLog
from app.models.leads.lead import Lead
from app.models.leads.lead_automation import LeadAutomation

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

        message = (
            f"New lead created: {event['lead'].name}"
            if event["type"] == "lead_created"
            else f"Lead moved to {str(to_status).capitalize()}"
        )

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
