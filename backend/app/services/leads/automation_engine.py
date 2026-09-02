from __future__ import annotations

import logging
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

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
]


class LeadStatusChangedEvent(TypedDict):
    type: str
    lead: Lead
    fromStatus: str
    toStatus: str


async def seed_default_automations(db: AsyncSession, organization_id: str) -> None:
    """Inserts the two default automations for an organization if they don't
    exist yet. Uses INSERT ... ON CONFLICT DO NOTHING against the
    (organization_id, name) unique constraint (see the leads-domain
    migration) rather than "check empty, then insert" — two concurrent
    first-ever GET /automations for the same new org would otherwise both
    observe an empty list and both insert, duplicating every row. The
    conflict target makes a duplicate insert a no-op instead, so this is
    safe to call every time regardless of how many requests race here.
    """
    stmt = pg_insert(LeadAutomation).values(
        [{**automation, "organization_id": organization_id} for automation in _DEFAULT_AUTOMATIONS]
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=["organization_id", "name"])
    await db.execute(stmt)
    await db.commit()


async def run_automations(db: AsyncSession, event: LeadStatusChangedEvent) -> list[str]:
    """Matches the event against every active LeadAutomation for the lead's
    organization. Partial trigger match: an automation with trigger_from/
    trigger_to left NULL matches any status on that side.

    Unrelated to app/automation/ (that package binds Workflows to Triggers —
    a different subsystem entirely; see LeadAutomation's own docstring).

    "log" writes to the server log via `logger.info()` — no UI concern, safe
    to do here. "notify" has no server-side channel to show a toast on, so
    its message is collected and returned instead; the route handler puts it
    on the HTTP response, and the frontend renders it as a toast from there.
    """
    stmt = select(LeadAutomation).where(
        LeadAutomation.organization_id == event["lead"].organization_id,
        LeadAutomation.active.is_(True),
        LeadAutomation.trigger_type == event["type"],
    )
    result = await db.execute(stmt)
    automations = result.scalars().all()

    notifications: list[str] = []

    for automation in automations:
        if automation.trigger_from is not None and automation.trigger_from != event["fromStatus"]:
            continue
        if automation.trigger_to is not None and automation.trigger_to != event["toStatus"]:
            continue

        if automation.action_type == "log":
            logger.info(
                "Automation triggered: %s (lead=%s, %s -> %s)",
                automation.name,
                event["lead"].id,
                event["fromStatus"],
                event["toStatus"],
            )
        elif automation.action_type == "notify":
            message = f"Lead moved to {event['toStatus'].capitalize()}"
            notifications.append(message)
            logger.info(
                "Automation triggered: %s (lead=%s) -> notify %r",
                automation.name,
                event["lead"].id,
                message,
            )

    return notifications
