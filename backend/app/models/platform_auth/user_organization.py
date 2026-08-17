from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.platform_auth.organization import PlatformOrganization
    from app.models.platform_auth.user import PlatformUser


class PlatformUserOrganization(Base):
    """Fase 1 (auth persistence). Genuine many-to-many membership: a user
    can belong to more than one organization (`PlatformAuth.
    add_user_to_organization()` already allows adding a user to an
    organization other than their own `organization_id` — see
    `test_add_user_to_organization_invalida_cache_do_usuario`) and an
    organization can have more than one member. This table is the source
    of truth for "who belongs to this organization" — `PlatformOrganization`
    itself carries no embedded users list.

    Composite primary key (user_email, organization_id) instead of a
    separate surrogate id: it's exactly the natural key of a membership,
    and it enforces "no duplicate membership row" at the database level
    without a separate unique constraint.

    `role` here is this user's role *within this specific membership*
    (independent of `PlatformUser.organization_role`, which is specifically
    their role in their *primary* organization) — a user added to a second
    organization via `add_user_to_organization()` starts as a plain
    "member" there, same as today's behavior.
    """

    __tablename__ = "user_organizations"

    user_email: Mapped[str] = mapped_column(
        String(255), ForeignKey("platform_users.email", ondelete="CASCADE"), primary_key=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("platform_organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, server_default="member")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["PlatformUser"] = relationship(back_populates="memberships")
    organization: Mapped["PlatformOrganization"] = relationship(back_populates="memberships")
