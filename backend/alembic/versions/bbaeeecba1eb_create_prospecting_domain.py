"""create prospecting domain

Revision ID: bbaeeecba1eb
Revises:
Create Date: 2026-07-29 00:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "bbaeeecba1eb"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    company_status = postgresql.ENUM(
        "lead",
        "qualifying",
        "in_negotiation",
        "customer",
        "inactive",
        "lost",
        name="company_status",
        create_type=False,
    )
    lead_source = postgresql.ENUM(
        "website",
        "referral",
        "social_media",
        "cold_outreach",
        "event",
        "inbound_form",
        "partner",
        "other",
        name="lead_source",
        create_type=False,
    )
    revenue_range = postgresql.ENUM(
        "up_to_360k",
        "from_360k_to_4_8m",
        "from_4_8m_to_300m",
        "above_300m",
        name="revenue_range",
        create_type=False,
    )
    contact_status = postgresql.ENUM(
        "active",
        "inactive",
        "left_company",
        "do_not_contact",
        name="contact_status",
        create_type=False,
    )
    campaign_status = postgresql.ENUM(
        "draft",
        "scheduled",
        "active",
        "paused",
        "completed",
        "cancelled",
        name="campaign_status",
        create_type=False,
    )
    campaign_channel = postgresql.ENUM(
        "email",
        "whatsapp",
        "linkedin",
        "phone",
        "event",
        "multi_channel",
        "other",
        name="campaign_channel",
        create_type=False,
    )
    campaign_company_status = postgresql.ENUM(
        "pending",
        "contacted",
        "engaged",
        "converted",
        "rejected",
        "removed",
        name="campaign_company_status",
        create_type=False,
    )
    interaction_type = postgresql.ENUM(
        "email",
        "call",
        "whatsapp",
        "linkedin",
        "meeting",
        "note",
        name="interaction_type",
        create_type=False,
    )

    for enum_type in (
        company_status,
        lead_source,
        revenue_range,
        contact_status,
        campaign_status,
        campaign_channel,
        campaign_company_status,
        interaction_type,
    ):
        enum_type.create(bind, checkfirst=True)

    # ---------- companies ----------
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("legal_name", sa.String(length=255), nullable=False),
        sa.Column("trade_name", sa.String(length=255), nullable=True),
        sa.Column("cnpj", sa.String(length=14), nullable=False),
        sa.Column("segment", sa.String(length=120), nullable=True),
        sa.Column("cnae", sa.String(length=10), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("instagram", sa.String(length=255), nullable=True),
        sa.Column("linkedin", sa.String(length=255), nullable=True),
        sa.Column("primary_phone", sa.String(length=20), nullable=True),
        sa.Column("primary_email", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column("zip_code", sa.String(length=9), nullable=True),
        sa.Column("employees_count_estimate", sa.Integer(), nullable=True),
        sa.Column("revenue_range_estimate", revenue_range, nullable=True),
        sa.Column("status", company_status, nullable=False, server_default="lead"),
        sa.Column("lead_source", lead_source, nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("cnpj ~ '^[0-9]{14}$'", name="ck_companies_cnpj_format"),
        sa.CheckConstraint("state IS NULL OR state ~ '^[A-Z]{2}$'", name="ck_companies_state_format"),
    )
    op.create_index("ix_companies_segment", "companies", ["segment"])
    op.create_index("ix_companies_primary_email", "companies", ["primary_email"])
    op.create_index("ix_companies_city", "companies", ["city"])
    op.create_index("ix_companies_state", "companies", ["state"])
    op.create_index("ix_companies_status", "companies", ["status"])
    op.create_index(
        "uq_companies_cnpj_active",
        "companies",
        ["cnpj"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # ---------- contacts ----------
    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("job_title", sa.String(length=120), nullable=True),
        sa.Column("department", sa.String(length=120), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("whatsapp", sa.String(length=20), nullable=True),
        sa.Column("linkedin", sa.String(length=255), nullable=True),
        sa.Column("is_decision_maker", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", contact_status, nullable=False, server_default="active"),
    )
    op.create_index("ix_contacts_company_id", "contacts", ["company_id"])
    op.create_index("ix_contacts_email", "contacts", ["email"])
    op.create_index("ix_contacts_status", "contacts", ["status"])

    # ---------- campaigns ----------
    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("status", campaign_status, nullable=False, server_default="draft"),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("channel", campaign_channel, nullable=False, server_default="email"),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_campaigns_end_after_start",
        ),
    )
    op.create_index("ix_campaigns_status", "campaigns", ["status"])
    op.create_index("ix_campaigns_channel", "campaigns", ["channel"])

    # ---------- campaign_companies ----------
    op.create_table(
        "campaign_companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", campaign_company_status, nullable=False, server_default="pending"),
        sa.Column(
            "included_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("result", sa.Text(), nullable=True),
    )
    op.create_index("ix_campaign_companies_campaign_id", "campaign_companies", ["campaign_id"])
    op.create_index("ix_campaign_companies_company_id", "campaign_companies", ["company_id"])
    op.create_index("ix_campaign_companies_status", "campaign_companies", ["status"])
    op.create_index(
        "uq_campaign_companies_active",
        "campaign_companies",
        ["campaign_id", "company_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # ---------- interactions ----------
    op.create_table(
        "interactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("type", interaction_type, nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("next_follow_up_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_interactions_company_id", "interactions", ["company_id"])
    op.create_index("ix_interactions_contact_id", "interactions", ["contact_id"])
    op.create_index("ix_interactions_campaign_id", "interactions", ["campaign_id"])
    op.create_index("ix_interactions_type", "interactions", ["type"])
    op.create_index("ix_interactions_occurred_at", "interactions", ["occurred_at"])
    op.create_index("ix_interactions_next_follow_up_at", "interactions", ["next_follow_up_at"])

    # ---------- email_templates ----------
    op.create_table(
        "email_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("content_html", sa.Text(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_email_templates_category", "email_templates", ["category"])
    op.create_index("ix_email_templates_is_active", "email_templates", ["is_active"])
    op.create_index(
        "uq_email_templates_name_version_active",
        "email_templates",
        ["name", "version"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # ---------- tags ----------
    op.create_table(
        "tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("color", sa.String(length=7), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.CheckConstraint("color IS NULL OR color ~ '^#[0-9A-Fa-f]{6}$'", name="ck_tags_color_hex"),
    )
    op.create_index(
        "uq_tags_name_active",
        "tags",
        ["name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # ---------- company_tags ----------
    op.create_table(
        "company_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tag_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tags.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_index("ix_company_tags_company_id", "company_tags", ["company_id"])
    op.create_index("ix_company_tags_tag_id", "company_tags", ["tag_id"])
    op.create_index(
        "uq_company_tags_active",
        "company_tags",
        ["company_id", "tag_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("company_tags")
    op.drop_table("tags")
    op.drop_table("email_templates")
    op.drop_table("interactions")
    op.drop_table("campaign_companies")
    op.drop_table("campaigns")
    op.drop_table("contacts")
    op.drop_table("companies")

    bind = op.get_bind()
    for enum_name in (
        "interaction_type",
        "campaign_company_status",
        "campaign_channel",
        "campaign_status",
        "contact_status",
        "revenue_range",
        "lead_source",
        "company_status",
    ):
        postgresql.ENUM(name=enum_name).drop(bind, checkfirst=True)
