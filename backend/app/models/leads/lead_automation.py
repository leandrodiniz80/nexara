from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import AuditMixin


class LeadAutomation(Base, AuditMixin):
    """A per-organization rule the leads automation engine
    (app/services/leads/automation_engine.py) matches lead status
    transitions against. Named `LeadAutomation`, not `Automation` — this
    codebase already has an unrelated `Automation` concept
    (app/automation/models/automation.py, a Workflow-trigger binding for a
    completely different subsystem); reusing the bare name here would
    collide conceptually even though the two live in different modules.

    Trigger/action are flattened columns (trigger_type/trigger_from/
    trigger_to, action_type) rather than a JSONB blob — there's exactly one
    trigger type today (lead_status_changed) and this keeps `WHERE
    trigger_from = ...` a real, indexable comparison instead of a JSON path
    expression.
    """

    __tablename__ = "automations"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_automations_org_name"),
    )

    organization_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("platform_organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    trigger_type: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="lead_status_changed"
    )
    trigger_from: Mapped[str | None] = mapped_column(String(32), nullable=True)
    trigger_to: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
