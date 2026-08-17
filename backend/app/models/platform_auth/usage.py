from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PlatformUsage(Base):
    """Fase 1 (auth persistence). Mirrors `PlatformAuth._usage[org_id]` —
    a per-organization, per-day request counter (`_usage_record()` resets
    it whenever the stored day no longer matches today). Composite primary
    key (organization_id, usage_date) is exactly that day-bucket, and
    naturally gives "one row per org per day" without a separate unique
    constraint — inserting a new day's row is just a new primary key, no
    reset logic needed in SQL itself (the reset-on-new-day behavior lives
    in the repository/service layer, same as it does in `PlatformAuth`
    today).
    """

    __tablename__ = "platform_usage"

    organization_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("platform_organizations.id", ondelete="CASCADE"), primary_key=True
    )
    usage_date: Mapped[date] = mapped_column(Date, primary_key=True)
    requests_today: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
