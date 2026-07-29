from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import AuditMixin
from app.models.prospecting.enums import (
    ProspectOrigin,
    ProspectPriority,
    ProspectStage,
    ProspectStatus,
    ProspectTemperature,
)

if TYPE_CHECKING:
    from app.models.mission.mission import Mission
    from app.models.prospecting.campaign import Campaign
    from app.models.prospecting.company import Company
    from app.models.prospecting.interaction import Interaction


class Prospect(Base, AuditMixin):
    """A commercial opportunity: one Company being pursued through one Campaign, within
    one Mission. Every Prospect belongs to exactly one Mission — it cannot exist outside
    of one (mission_id mirrors campaign.mission_id; kept as its own column rather than
    derived through the campaign join so "which mission is this prospect part of" is a
    direct, indexed fact rather than requiring a join every time it's queried).

    This is the aggregate root of the sales process. A Company can have many Prospects
    (one per opportunity/campaign, including reopened attempts); each Prospect has its
    own funnel position, score, and timeline, independent of the others.
    """

    __tablename__ = "prospects"
    __table_args__ = (
        CheckConstraint("score IS NULL OR (score BETWEEN 0 AND 100)", name="ck_prospects_score_range"),
        CheckConstraint(
            "probability IS NULL OR (probability BETWEEN 0 AND 100)",
            name="ck_prospects_probability_range",
        ),
        CheckConstraint(
            "estimated_value IS NULL OR estimated_value >= 0", name="ck_prospects_estimated_value_positive"
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # References the future users domain (sales rep responsible); no FK yet, see AuditMixin.
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    status: Mapped[ProspectStatus] = mapped_column(
        SAEnum(ProspectStatus, name="prospect_status", native_enum=True),
        nullable=False,
        default=ProspectStatus.OPEN,
        index=True,
    )
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    temperature: Mapped[ProspectTemperature] = mapped_column(
        SAEnum(ProspectTemperature, name="prospect_temperature", native_enum=True),
        nullable=False,
        default=ProspectTemperature.COLD,
        index=True,
    )
    origin: Mapped[ProspectOrigin | None] = mapped_column(
        SAEnum(ProspectOrigin, name="prospect_origin", native_enum=True), nullable=True
    )
    priority: Mapped[ProspectPriority] = mapped_column(
        SAEnum(ProspectPriority, name="prospect_priority", native_enum=True),
        nullable=False,
        default=ProspectPriority.NORMAL,
        index=True,
    )
    current_stage: Mapped[ProspectStage] = mapped_column(
        SAEnum(ProspectStage, name="prospect_stage", native_enum=True),
        nullable=False,
        default=ProspectStage.NEW,
        index=True,
    )

    qualified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lost_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_interaction_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    next_action_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    reason_lost: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_value: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    probability: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    company: Mapped["Company"] = relationship(back_populates="prospects")
    campaign: Mapped["Campaign"] = relationship(back_populates="prospects")
    mission: Mapped["Mission"] = relationship(back_populates="prospects")
    interactions: Mapped[list["Interaction"]] = relationship(
        back_populates="prospect", cascade="all, delete-orphan"
    )
