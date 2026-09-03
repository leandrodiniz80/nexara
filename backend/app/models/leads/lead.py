from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import AuditMixin


class Lead(Base, AuditMixin):
    """A prospecting lead captured by a tenant. Deliberately separate from the
    existing Prospect aggregate (app/models/prospecting) — Prospect requires a
    Mission and a Campaign to exist first (both NOT NULL FKs, see
    docs/domain-mission.md), and the frontend's standalone Leads feature has
    no Mission/Campaign concept yet. This is the simple table that feature
    already assumes; unifying it with Prospect is a separate, larger project.
    """

    __tablename__ = "leads"
    __table_args__ = (
        CheckConstraint("status IN ('new','contacted','converted','lost')", name="ck_leads_status"),
        CheckConstraint("score >= 0 AND score <= 100", name="ck_leads_score"),
        # Backs GET /leads: WHERE organization_id = ... ORDER BY created_at
        # DESC. The plain ix_leads_org_id index alone still answers the
        # filter correctly; this composite one avoids a separate sort step
        # once an organization's lead count is large enough to matter.
        Index("ix_leads_org_id_created_at", "organization_id", "created_at"),
        # Backs GET /leads/attention: WHERE organization_id = ... AND status
        # IN (...) ORDER BY updated_at ASC.
        Index("ix_leads_org_id_status_updated_at", "organization_id", "status", "updated_at"),
        # Backs GET /leads/tasks: WHERE organization_id = ... AND
        # next_action_due_at IS NOT NULL ORDER BY next_action_due_at ASC.
        Index("ix_leads_org_id_next_action_due_at", "organization_id", "next_action_due_at"),
        Index("ix_leads_owner_email", "owner_email"),
        # Backs GET /workday/next's "does this user already have a lead in
        # focus" check: WHERE organization_id = ... AND focused_by_email = ...
        Index("ix_leads_org_id_focused_by_email", "organization_id", "focused_by_email"),
    )

    organization_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("platform_organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, server_default="")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="new", index=True
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_action_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # References platform_users.email (this codebase's real user identity —
    # there is no users.id UUID table) rather than a bare unenforced UUID
    # placeholder like AuditMixin's created_by/updated_by: real referential
    # integrity now, no rework once a proper users table might exist later.
    owner_email: Mapped[str | None] = mapped_column(
        String(255), ForeignKey("platform_users.email", ondelete="SET NULL"), nullable=True
    )
    # Workday mode's execution lock — "only one lead in focus per user" is
    # enforced in the router (GET /workday/next), not by a DB constraint;
    # focused_by_email is who currently holds it (distinct from owner_email:
    # any user working their queue can bring an unowned or someone-else's
    # lead into focus, not just its owner).
    in_focus: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    focused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    focused_by_email: Mapped[str | None] = mapped_column(
        String(255), ForeignKey("platform_users.email", ondelete="SET NULL"), nullable=True
    )
