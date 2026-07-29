"""create mission domain

Introduces Mission as the platform's top-level aggregate: creates missions,
mission_metrics (1:1) and mission_events tables, and makes every Campaign/Prospect
belong to a Mission (mission_id, NOT NULL FK on both).

Revision ID: 9a9d9f54336a
Revises: 621b99b1a9ed
Create Date: 2026-07-29 00:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "9a9d9f54336a"
down_revision: Union[str, None] = "621b99b1a9ed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    mission_status = postgresql.ENUM(
        "draft",
        "planning",
        "running",
        "paused",
        "finished",
        "cancelled",
        name="mission_status",
        create_type=False,
    )
    mission_priority = postgresql.ENUM(
        "low", "normal", "high", "critical", name="mission_priority", create_type=False
    )
    for enum_type in (mission_status, mission_priority):
        enum_type.create(bind, checkfirst=True)

    # ---------- missions ----------
    op.create_table(
        "missions",
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
        sa.Column("status", mission_status, nullable=False, server_default="draft"),
        sa.Column("priority", mission_priority, nullable=False, server_default="normal"),
        sa.Column("target_segment", sa.String(length=120), nullable=True),
        sa.Column("target_region", sa.String(length=120), nullable=True),
        sa.Column("target_city", sa.String(length=120), nullable=True),
        sa.Column("target_state", sa.String(length=2), nullable=True),
        sa.Column("target_quantity", sa.Integer(), nullable=True),
        sa.Column("target_meetings", sa.Integer(), nullable=True),
        sa.Column("target_contracts", sa.Integer(), nullable=True),
        sa.Column("target_revenue", sa.Numeric(14, 2), nullable=True),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=True),
        sa.Column("estimated_completion", sa.Date(), nullable=True),
        sa.CheckConstraint("progress IS NULL OR (progress BETWEEN 0 AND 100)", name="ck_missions_progress_range"),
        sa.CheckConstraint(
            "target_quantity IS NULL OR target_quantity >= 0", name="ck_missions_target_quantity_positive"
        ),
        sa.CheckConstraint(
            "target_meetings IS NULL OR target_meetings >= 0", name="ck_missions_target_meetings_positive"
        ),
        sa.CheckConstraint(
            "target_contracts IS NULL OR target_contracts >= 0", name="ck_missions_target_contracts_positive"
        ),
        sa.CheckConstraint(
            "target_revenue IS NULL OR target_revenue >= 0", name="ck_missions_target_revenue_positive"
        ),
        sa.CheckConstraint(
            "finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at",
            name="ck_missions_finished_after_started",
        ),
        sa.CheckConstraint(
            "target_state IS NULL OR target_state ~ '^[A-Z]{2}$'", name="ck_missions_target_state_format"
        ),
    )
    op.create_index("ix_missions_status", "missions", ["status"])
    op.create_index("ix_missions_priority", "missions", ["priority"])
    op.create_index("ix_missions_target_segment", "missions", ["target_segment"])
    op.create_index("ix_missions_target_city", "missions", ["target_city"])
    op.create_index("ix_missions_target_state", "missions", ["target_state"])
    op.create_index("ix_missions_deadline", "missions", ["deadline"])
    op.create_index("ix_missions_owner_id", "missions", ["owner_id"])

    # ---------- mission_metrics (1:1) ----------
    op.create_table(
        "mission_metrics",
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
            "mission_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("companies_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("companies_qualified", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prospects_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("emails_generated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("emails_approved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("emails_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("emails_opened", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("emails_replied", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("meetings", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("proposals", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("contracts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("won_value", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("lost_value", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("conversion_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("response_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("meeting_rate", sa.Numeric(5, 2), nullable=True),
        sa.CheckConstraint(
            "conversion_rate IS NULL OR (conversion_rate BETWEEN 0 AND 100)",
            name="ck_mission_metrics_conversion_rate_range",
        ),
        sa.CheckConstraint(
            "response_rate IS NULL OR (response_rate BETWEEN 0 AND 100)",
            name="ck_mission_metrics_response_rate_range",
        ),
        sa.CheckConstraint(
            "meeting_rate IS NULL OR (meeting_rate BETWEEN 0 AND 100)",
            name="ck_mission_metrics_meeting_rate_range",
        ),
    )
    op.create_index(
        "uq_mission_metrics_mission_id_active",
        "mission_metrics",
        ["mission_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # ---------- mission_events ----------
    op.create_table(
        "mission_events",
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
            "mission_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("event_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_mission_events_mission_id", "mission_events", ["mission_id"])
    op.create_index("ix_mission_events_event", "mission_events", ["event"])
    op.create_index("ix_mission_events_occurred_at", "mission_events", ["occurred_at"])

    # ---------- Campaign/Prospect must belong to a Mission ----------
    op.add_column(
        "campaigns",
        sa.Column(
            "mission_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_index("ix_campaigns_mission_id", "campaigns", ["mission_id"])

    op.add_column(
        "prospects",
        sa.Column(
            "mission_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_index("ix_prospects_mission_id", "prospects", ["mission_id"])


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_column("prospects", "mission_id")
    op.drop_column("campaigns", "mission_id")

    op.drop_table("mission_events")
    op.drop_table("mission_metrics")
    op.drop_table("missions")

    for enum_name in ("mission_priority", "mission_status"):
        postgresql.ENUM(name=enum_name).drop(bind, checkfirst=True)
