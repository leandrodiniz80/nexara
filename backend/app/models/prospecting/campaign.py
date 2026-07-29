from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import AuditMixin
from app.models.prospecting.enums import CampaignChannel, CampaignStatus

if TYPE_CHECKING:
    from app.models.mission.mission import Mission
    from app.models.prospecting.prospect import Prospect


class Campaign(Base, AuditMixin):
    """A prospecting campaign. Always belongs to a Mission — a Campaign cannot exist
    outside of one. Companies are linked to it only through Prospect (the commercial
    opportunity), never directly."""

    __tablename__ = "campaigns"
    __table_args__ = (
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_campaigns_end_after_start",
        ),
    )

    mission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[CampaignStatus] = mapped_column(
        SAEnum(CampaignStatus, name="campaign_status", native_enum=True),
        nullable=False,
        default=CampaignStatus.DRAFT,
        index=True,
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    channel: Mapped[CampaignChannel] = mapped_column(
        SAEnum(CampaignChannel, name="campaign_channel", native_enum=True),
        nullable=False,
        default=CampaignChannel.EMAIL,
        index=True,
    )
    # References the future users domain (owner/responsible); no FK yet, see AuditMixin.
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    mission: Mapped["Mission"] = relationship(back_populates="campaigns")
    prospects: Mapped[list["Prospect"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
