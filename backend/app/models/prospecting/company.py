from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Index, Integer, String, Text, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import AuditMixin
from app.models.prospecting.enums import RevenueRange

if TYPE_CHECKING:
    from app.models.prospecting.company_tag import CompanyTag
    from app.models.prospecting.contact import Contact
    from app.models.prospecting.prospect import Prospect


class Company(Base, AuditMixin):
    """A single, real-world company (e.g. "Coca-Cola"). Pure registry data: identity,
    firmographics, contact info. Never duplicated, never carries commercial-process state.

    Commercial opportunities against this company are modeled by `Prospect`, not here.
    """

    __tablename__ = "companies"
    __table_args__ = (
        CheckConstraint("cnpj ~ '^[0-9]{14}$'", name="ck_companies_cnpj_format"),
        CheckConstraint("state IS NULL OR state ~ '^[A-Z]{2}$'", name="ck_companies_state_format"),
        # Partial unique index instead of a plain unique constraint: soft-deleted rows keep
        # occupying the table, so uniqueness must only be enforced among active records.
        Index(
            "uq_companies_cnpj_active", "cnpj", unique=True, postgresql_where=text("deleted_at IS NULL")
        ),
    )

    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cnpj: Mapped[str] = mapped_column(String(14), nullable=False)
    segment: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    cnae: Mapped[str | None] = mapped_column(String(10), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    instagram: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin: Mapped[str | None] = mapped_column(String(255), nullable=True)
    primary_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    primary_email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    zip_code: Mapped[str | None] = mapped_column(String(9), nullable=True)
    employees_count_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    revenue_range_estimate: Mapped[RevenueRange | None] = mapped_column(
        SAEnum(RevenueRange, name="revenue_range", native_enum=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    contacts: Mapped[list["Contact"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    prospects: Mapped[list["Prospect"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    tag_links: Mapped[list["CompanyTag"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
