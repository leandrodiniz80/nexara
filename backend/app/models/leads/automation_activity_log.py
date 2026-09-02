from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AutomationActivityLog(Base):
    """Append-only feed of every automation firing (both "log" and "notify"
    action types), across all leads in an organization — same rationale as
    LeadStatusHistory: written once, never updated, so no AuditMixin.

    lead_name/automation_name are denormalized snapshots taken at firing
    time, not FKs resolved at read time — this is a display-only activity
    feed, not a join target, so GET /automations/activity stays a single-
    table SELECT ... ORDER BY created_at DESC LIMIT."""

    __tablename__ = "automation_activity_log"
    __table_args__ = (
        Index("ix_automation_activity_log_org_id_created_at", "organization_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("platform_organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_name: Mapped[str] = mapped_column(String(255), nullable=False)
    automation_name: Mapped[str] = mapped_column(String(255), nullable=False)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
