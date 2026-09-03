from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LeadActivityLog(Base):
    """Append-only feed of manual, non-automation lead events — owner
    reassignment, notes/next_action edits, task completions — that don't fit
    LeadStatusHistory (status-transition-shaped: from_status/to_status) or
    AutomationActivityLog (automation-shaped: automation_name/action_type).
    GET /leads/{id}/timeline and GET /leads/activity merge all three tables
    rather than overloading either existing one with a semantically
    unrelated event type.

    lead_name is a denormalized snapshot (same rationale as
    AutomationActivityLog.lead_name), so the org-wide feed stays a
    single-table SELECT with no join.
    """

    __tablename__ = "lead_activity_log"
    __table_args__ = (
        Index("ix_lead_activity_log_lead_id_created_at", "lead_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("platform_organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    lead_name: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # Both added for workday mode: user_email attributes an entry to whoever
    # was in the session when it happened (only populated where a caller
    # session actually exists — automation-driven entries have none, so it
    # stays null there); duration_seconds is set only for a task_completed
    # entry that ended an active focus session. Structured (not folded into
    # `message`) since these are meant as a real base for future
    # productivity/analytics, not just human-readable text.
    user_email: Mapped[str | None] = mapped_column(
        String(255), ForeignKey("platform_users.email", ondelete="SET NULL"), nullable=True
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
