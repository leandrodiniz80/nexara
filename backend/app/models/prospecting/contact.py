from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import AuditMixin
from app.models.prospecting.enums import ContactStatus

if TYPE_CHECKING:
    from app.models.prospecting.company import Company
    from app.models.prospecting.interaction import Interaction


class Contact(Base, AuditMixin):
    """A person at a Company who can be reached during prospecting."""

    __tablename__ = "contacts"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    whatsapp: Mapped[str | None] = mapped_column(String(20), nullable=True)
    linkedin: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_decision_maker: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[ContactStatus] = mapped_column(
        SAEnum(ContactStatus, name="contact_status", native_enum=True),
        nullable=False,
        default=ContactStatus.ACTIVE,
        index=True,
    )

    company: Mapped["Company"] = relationship(back_populates="contacts")
    # No delete-orphan here: the FK is ON DELETE SET NULL, so interactions
    # outlive the contact they were originally logged against.
    interactions: Mapped[list["Interaction"]] = relationship(back_populates="contact")
