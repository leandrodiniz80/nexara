"""introduce prospect aggregate, drop campaign_companies

Splits "company" (registry) from "commercial opportunity" (Prospect). Company loses its
pipeline fields (status, lead_source); CampaignCompany is dropped and replaced by the
new Prospect aggregate; Interaction moves from Company/Campaign to Prospect.

Revision ID: 621b99b1a9ed
Revises: bbaeeecba1eb
Create Date: 2026-07-29 00:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "621b99b1a9ed"
down_revision: Union[str, None] = "bbaeeecba1eb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # ---------- 1. drop CampaignCompany (superseded by Prospect) ----------
    op.drop_table("campaign_companies")
    postgresql.ENUM(name="campaign_company_status").drop(bind, checkfirst=True)

    # ---------- 2. strip pipeline fields off Company ----------
    # Dropping a column also drops indexes/constraints/FKs that depend solely on it.
    op.drop_column("companies", "status")
    op.drop_column("companies", "lead_source")
    postgresql.ENUM(name="company_status").drop(bind, checkfirst=True)
    postgresql.ENUM(name="lead_source").drop(bind, checkfirst=True)

    # ---------- 3. create Prospect enums ----------
    prospect_status = postgresql.ENUM(
        "open", "won", "lost", "disqualified", name="prospect_status", create_type=False
    )
    prospect_stage = postgresql.ENUM(
        "new",
        "researching",
        "qualified",
        "contact_ready",
        "email_pending_approval",
        "email_sent",
        "follow_up",
        "responded",
        "meeting",
        "proposal",
        "negotiation",
        "won",
        "lost",
        name="prospect_stage",
        create_type=False,
    )
    prospect_temperature = postgresql.ENUM(
        "cold", "warm", "hot", name="prospect_temperature", create_type=False
    )
    prospect_priority = postgresql.ENUM(
        "low", "normal", "high", "urgent", name="prospect_priority", create_type=False
    )
    prospect_origin = postgresql.ENUM(
        "website",
        "referral",
        "social_media",
        "cold_outreach",
        "event",
        "inbound_form",
        "partner",
        "other",
        name="prospect_origin",
        create_type=False,
    )
    for enum_type in (
        prospect_status,
        prospect_stage,
        prospect_temperature,
        prospect_priority,
        prospect_origin,
    ):
        enum_type.create(bind, checkfirst=True)

    # ---------- 4. create prospects ----------
    op.create_table(
        "prospects",
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
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", prospect_status, nullable=False, server_default="open"),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("temperature", prospect_temperature, nullable=False, server_default="cold"),
        sa.Column("origin", prospect_origin, nullable=True),
        sa.Column("priority", prospect_priority, nullable=False, server_default="normal"),
        sa.Column("current_stage", prospect_stage, nullable=False, server_default="new"),
        sa.Column("qualified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lost_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_interaction_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_action_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason_lost", sa.Text(), nullable=True),
        sa.Column("estimated_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("probability", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("score IS NULL OR (score BETWEEN 0 AND 100)", name="ck_prospects_score_range"),
        sa.CheckConstraint(
            "probability IS NULL OR (probability BETWEEN 0 AND 100)",
            name="ck_prospects_probability_range",
        ),
        sa.CheckConstraint(
            "estimated_value IS NULL OR estimated_value >= 0",
            name="ck_prospects_estimated_value_positive",
        ),
    )
    op.create_index("ix_prospects_company_id", "prospects", ["company_id"])
    op.create_index("ix_prospects_campaign_id", "prospects", ["campaign_id"])
    op.create_index("ix_prospects_owner_id", "prospects", ["owner_id"])
    op.create_index("ix_prospects_status", "prospects", ["status"])
    op.create_index("ix_prospects_temperature", "prospects", ["temperature"])
    op.create_index("ix_prospects_priority", "prospects", ["priority"])
    op.create_index("ix_prospects_current_stage", "prospects", ["current_stage"])
    op.create_index("ix_prospects_last_interaction_at", "prospects", ["last_interaction_at"])
    op.create_index("ix_prospects_next_action_at", "prospects", ["next_action_at"])

    # ---------- 5. move Interaction from Company/Campaign to Prospect ----------
    op.drop_column("interactions", "company_id")
    op.drop_column("interactions", "campaign_id")
    op.add_column(
        "interactions",
        sa.Column(
            "prospect_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prospects.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_index("ix_interactions_prospect_id", "interactions", ["prospect_id"])


def downgrade() -> None:
    bind = op.get_bind()

    # ---------- revert Interaction ----------
    op.drop_column("interactions", "prospect_id")
    op.add_column(
        "interactions",
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "interactions",
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_index("ix_interactions_campaign_id", "interactions", ["campaign_id"])
    op.create_index("ix_interactions_company_id", "interactions", ["company_id"])

    # ---------- drop prospects + its enums ----------
    op.drop_table("prospects")
    for enum_name in (
        "prospect_origin",
        "prospect_priority",
        "prospect_temperature",
        "prospect_stage",
        "prospect_status",
    ):
        postgresql.ENUM(name=enum_name).drop(bind, checkfirst=True)

    # ---------- restore Company pipeline fields ----------
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
    company_status.create(bind, checkfirst=True)
    lead_source.create(bind, checkfirst=True)
    op.add_column(
        "companies",
        sa.Column("status", company_status, nullable=False, server_default="lead"),
    )
    op.add_column("companies", sa.Column("lead_source", lead_source, nullable=True))
    op.create_index("ix_companies_status", "companies", ["status"])

    # ---------- restore campaign_companies ----------
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
    campaign_company_status.create(bind, checkfirst=True)
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
