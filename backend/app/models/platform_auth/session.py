from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.platform_auth.organization import PlatformOrganization
    from app.models.platform_auth.user import PlatformUser


class PlatformSession(Base):
    """Fase 1 (auth persistence). Did not exist in any form before this
    sprint: `PlatformAuth._persist()` only ever wrote users/organizations/
    usage to storage — `self._sessions` was never included, so a session
    could never have survived a restart even with `PostgresStorage` wired
    in. This table is what actually fixes that.

    `token` (the signed, HMAC-verified string the client holds) is the
    primary key — it's already the unique key `PlatformAuth._sessions`
    dict uses today, and it's what every lookup (`get_session`) is keyed
    by. `role`/`permissions` are a snapshot taken at login time, not a
    live join to `platform_users` — matching today's exact behavior where
    a role change after login only takes effect on the next login, not
    retroactively on existing sessions. `expires_at` is computed once at
    write time (`issued_at + ttl`) rather than recomputed from `issued_at`
    on every read.
    """

    __tablename__ = "platform_sessions"

    token: Mapped[str] = mapped_column(Text, primary_key=True)
    user_email: Mapped[str] = mapped_column(
        String(255), ForeignKey("platform_users.email", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("platform_organizations.id", ondelete="SET NULL"), nullable=True
    )
    role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    permissions: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    user: Mapped["PlatformUser"] = relationship()
    organization: Mapped["PlatformOrganization | None"] = relationship(back_populates="sessions")
