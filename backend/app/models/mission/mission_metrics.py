from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import AuditMixin

if TYPE_CHECKING:
    from app.models.mission.mission import Mission


class MissionMetrics(Base, AuditMixin):
    """1:1 snapshot of a Mission's numbers, recomputed by MissionEngine.calculate_metrics().

    Kept as a persisted snapshot rather than computed on every read: emails_generated/
    approved/sent/opened/replied have no source-of-truth table yet (no email-sending
    pipeline exists in this codebase), so those five counters are accumulators meant to
    be incremented by future integration points (CopyAgent, ReviewAgent, an eventual
    send/webhook handler) — calculate_metrics() does not overwrite them; it only
    recomputes what is actually derivable today from Prospect data.
    """

    __tablename__ = "mission_metrics"
    __table_args__ = (
        CheckConstraint(
            "conversion_rate IS NULL OR (conversion_rate BETWEEN 0 AND 100)",
            name="ck_mission_metrics_conversion_rate_range",
        ),
        CheckConstraint(
            "response_rate IS NULL OR (response_rate BETWEEN 0 AND 100)",
            name="ck_mission_metrics_response_rate_range",
        ),
        CheckConstraint(
            "meeting_rate IS NULL OR (meeting_rate BETWEEN 0 AND 100)",
            name="ck_mission_metrics_meeting_rate_range",
        ),
        # Partial unique index enforcing the 1:1 with Mission (soft-delete safe, same
        # pattern used across the rest of the schema).
        Index(
            "uq_mission_metrics_mission_id_active",
            "mission_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    mission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False
    )

    companies_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    companies_qualified: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    prospects_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    emails_generated: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    emails_approved: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    emails_sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    emails_opened: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    emails_replied: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    meetings: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    proposals: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    contracts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    won_value: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    lost_value: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    conversion_rate: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    response_rate: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    meeting_rate: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    mission: Mapped["Mission"] = relationship(back_populates="metrics")
