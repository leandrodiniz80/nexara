from __future__ import annotations

from sqlalchemy import Boolean, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import AuditMixin


class EmailTemplate(Base, AuditMixin):
    """A reusable, versioned email template used in prospecting outreach."""

    __tablename__ = "email_templates"
    __table_args__ = (
        Index(
            "uq_email_templates_name_version_active",
            "name",
            "version",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    content_html: Mapped[str] = mapped_column(Text, nullable=False)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
