from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import AuditMixin

if TYPE_CHECKING:
    from app.models.mission.mission import Mission


class MissionEvent(Base, AuditMixin):
    """One row of a Mission's timeline (see MissionTimeline, the service-layer helper
    that writes/reads these). `event` is a free-form string catalogue ("mission_created",
    "campaign_created", "research_started", "first_meeting", ...) rather than a closed
    enum: the set of event kinds is expected to keep growing as features ship, and a
    native enum would force a migration for every new kind.

    The spec's "timestamp" field is named `occurred_at` here to match the existing
    convention (see Interaction.occurred_at) — the logical time of the event, as
    opposed to `created_at` (AuditMixin), which is when the row was written. Likewise
    "metadata" is named `event_metadata`: `metadata` is a reserved attribute on every
    SQLAlchemy declarative model (it's `Base.metadata`, the schema's MetaData object).
    """

    __tablename__ = "mission_events"

    mission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    mission: Mapped["Mission"] = relationship(back_populates="events")
