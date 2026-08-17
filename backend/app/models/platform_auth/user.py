from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.platform_auth.organization import PlatformOrganization
    from app.models.platform_auth.user_organization import PlatformUserOrganization


class PlatformUser(Base):
    """Fase 1 (auth persistence). Mirrors `PlatformAuth._users[email]` — a
    plain dict keyed by email today, with no separate user id anywhere in
    the codebase (every one of the 433 call sites into PlatformAuth
    addresses a user by email, never by an id). `email` is the primary key
    on purpose, not a surrogate uuid: adding one would have zero consumers
    and would only be an unused column.

    `organization_id`/`organization_role` are this user's *primary* (home)
    organization — the single value `get_user_organization()`/
    `get_user_organization_role()` return, unchanged in shape from today.
    Genuine multi-organization membership (a user belonging to more than
    one organization, as `add_user_to_organization()` already allows) is
    tracked separately in `PlatformUserOrganization`, not here.
    """

    __tablename__ = "platform_users"

    email: Mapped[str] = mapped_column(String(255), primary_key=True)
    password_salt: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    password_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, server_default="user")
    permissions: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    organization_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("platform_organizations.id", ondelete="SET NULL"), nullable=True
    )
    organization_role: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="member"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    organization: Mapped["PlatformOrganization | None"] = relationship(back_populates="users")
    memberships: Mapped[list["PlatformUserOrganization"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
