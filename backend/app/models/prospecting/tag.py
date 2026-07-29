from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import AuditMixin

if TYPE_CHECKING:
    from app.models.prospecting.company_tag import CompanyTag


class Tag(Base, AuditMixin):
    """A label that can be attached to companies for freeform segmentation."""

    __tablename__ = "tags"
    __table_args__ = (
        CheckConstraint("color IS NULL OR color ~ '^#[0-9A-Fa-f]{6}$'", name="ck_tags_color_hex"),
        Index("uq_tags_name_active", "name", unique=True, postgresql_where=text("deleted_at IS NULL")),
    )

    name: Mapped[str] = mapped_column(String(80), nullable=False)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    company_links: Mapped[list["CompanyTag"]] = relationship(
        back_populates="tag", cascade="all, delete-orphan"
    )
