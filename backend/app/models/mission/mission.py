from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, Integer, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mission.enums import MissionPriority, MissionStatus
from app.models.mixins import AuditMixin

if TYPE_CHECKING:
    from app.models.mission.mission_event import MissionEvent
    from app.models.mission.mission_metrics import MissionMetrics
    from app.models.prospecting.campaign import Campaign
    from app.models.prospecting.prospect import Prospect


class Mission(Base, AuditMixin):
    """The platform's top-level aggregate root: a commercial objective ("find and close
    N deals in segment X by date Y"). Every Campaign and every Prospect belongs to
    exactly one Mission — neither can exist outside of one.
    """

    __tablename__ = "missions"
    __table_args__ = (
        CheckConstraint("progress IS NULL OR (progress BETWEEN 0 AND 100)", name="ck_missions_progress_range"),
        CheckConstraint(
            "target_quantity IS NULL OR target_quantity >= 0", name="ck_missions_target_quantity_positive"
        ),
        CheckConstraint(
            "target_meetings IS NULL OR target_meetings >= 0", name="ck_missions_target_meetings_positive"
        ),
        CheckConstraint(
            "target_contracts IS NULL OR target_contracts >= 0", name="ck_missions_target_contracts_positive"
        ),
        CheckConstraint(
            "target_revenue IS NULL OR target_revenue >= 0", name="ck_missions_target_revenue_positive"
        ),
        CheckConstraint(
            "finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at",
            name="ck_missions_finished_after_started",
        ),
        CheckConstraint(
            "target_state IS NULL OR target_state ~ '^[A-Z]{2}$'", name="ck_missions_target_state_format"
        ),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[MissionStatus] = mapped_column(
        SAEnum(MissionStatus, name="mission_status", native_enum=True),
        nullable=False,
        default=MissionStatus.DRAFT,
        index=True,
    )
    priority: Mapped[MissionPriority] = mapped_column(
        SAEnum(MissionPriority, name="mission_priority", native_enum=True),
        nullable=False,
        default=MissionPriority.NORMAL,
        index=True,
    )
    target_segment: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    target_region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    target_city: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    target_state: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    target_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_meetings: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_contracts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_revenue: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # References the future users domain (owner/responsible); no FK yet, see AuditMixin.
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    progress: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_completion: Mapped[date | None] = mapped_column(Date, nullable=True)

    campaigns: Mapped[list["Campaign"]] = relationship(
        back_populates="mission", cascade="all, delete-orphan"
    )
    prospects: Mapped[list["Prospect"]] = relationship(
        back_populates="mission", cascade="all, delete-orphan"
    )
    metrics: Mapped["MissionMetrics | None"] = relationship(
        back_populates="mission", uselist=False, cascade="all, delete-orphan"
    )
    events: Mapped[list["MissionEvent"]] = relationship(
        back_populates="mission", cascade="all, delete-orphan", order_by="MissionEvent.occurred_at"
    )
