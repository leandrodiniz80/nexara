from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
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
