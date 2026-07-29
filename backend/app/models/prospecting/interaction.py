from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import AuditMixin
from app.models.prospecting.enums import InteractionType

if TYPE_CHECKING:
    from app.models.prospecting.contact import Contact
    from app.models.prospecting.prospect import Prospect


class Interaction(Base, AuditMixin):
    """A logged touchpoint against a Prospect (and optionally a specific Contact).

    Interactions belong to the commercial process (Prospect), not to the Company: the
    same company can have independent interaction histories on different opportunities.
    """

    __tablename__ = "interactions"

    prospect_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    type: Mapped[InteractionType] = mapped_column(
        SAEnum(InteractionType, name="interaction_type", native_enum=True), nullable=False, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_follow_up_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    prospect: Mapped["Prospect"] = relationship(back_populates="interactions")
    contact: Mapped["Contact | None"] = relationship(back_populates="interactions")
