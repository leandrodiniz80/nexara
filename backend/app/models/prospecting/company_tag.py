from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import AuditMixin

if TYPE_CHECKING:
    from app.models.prospecting.company import Company
    from app.models.prospecting.tag import Tag


class CompanyTag(Base, AuditMixin):
    """Association entity: many-to-many link between Company and Tag."""

    __tablename__ = "company_tags"
    __table_args__ = (
        Index(
            "uq_company_tags_active",
            "company_id",
            "tag_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, index=True
    )

    company: Mapped["Company"] = relationship(back_populates="tag_links")
    tag: Mapped["Tag"] = relationship(back_populates="company_links")
