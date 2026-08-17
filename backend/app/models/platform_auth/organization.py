from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.platform_auth.session import PlatformSession
    from app.models.platform_auth.user import PlatformUser
    from app.models.platform_auth.user_organization import PlatformUserOrganization


class PlatformOrganization(Base):
    """Fase 1 (auth persistence). A tenant/organization — mirrors exactly what
    `PlatformAuth._organizations[org_id]` holds today as a plain dict, now a
    real row. `id` is a plain string, not a native Postgres UUID, on purpose:
    `PlatformAuth.create_organization()` generates it as `uuid.uuid4().hex`
    (32 lowercase hex chars, no dashes) and this id is threaded through
    Stripe metadata, cache keys and every organization_id string comparison
    in the codebase today — a native UUID column would silently reformat it
    (dashes) and break every one of those.

    No `AuditMixin` here: that mixin's own `created_by`/`updated_by` are
    documented as "add the FK to users.id once that domain exists" — but
    this *is* that users domain now, and "which user created this
    organization" isn't a concept `PlatformAuth` tracks today (self-registration
    creates an organization with no acting user yet). Kept to exactly the
    fields `PlatformAuth` already reads/writes.
    """

    __tablename__ = "platform_organizations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[str] = mapped_column(String(32), nullable=False, server_default="free")
    plan_history: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    retention_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    lead_states: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subscription_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    users: Mapped[list["PlatformUser"]] = relationship(back_populates="organization")
    memberships: Mapped[list["PlatformUserOrganization"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["PlatformSession"]] = relationship(back_populates="organization")
