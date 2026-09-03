from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserNotification(Base):
    """Persistent counterpart to the ephemeral toast messages
    run_automations() has always returned — a "notify" automation firing
    now also lands here (for the lead's owner, if one is assigned; an
    unowned lead still gets the toast, just no row here — there's no single
    clear recipient otherwise), so the value isn't lost the moment the toast
    fades. lead_id is nullable and beyond the literal notification schema
    this round's spec listed, added because the UI requirement right next
    to it ("clicking opens the lead, if applicable") is otherwise
    unimplementable. No AuditMixin: nothing here is ever updated except the
    one `read` flag flip, not the audit trail's created_by/updated_by/
    deleted_at shape.
    """

    __tablename__ = "user_notifications"
    __table_args__ = (
        Index(
            "ix_user_notifications_org_user_created_at",
            "organization_id",
            "user_email",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("platform_organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_email: Mapped[str] = mapped_column(
        String(255), ForeignKey("platform_users.email", ondelete="CASCADE"), nullable=False
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
