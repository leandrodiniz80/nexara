"""create automation_activity_log

New append-only table backing GET /automations/activity — one row per
automation firing (both "log" and "notify" action types), written by
run_automations() alongside its existing logger.info() calls. Denormalizes
lead_name/automation_name at write time so the feed query stays a single-
table SELECT ... ORDER BY created_at DESC LIMIT, no joins.

Revision ID: f1c4b8a3d6e9
Revises: a3f9c1e6b7d2
Create Date: 2026-09-02 00:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f1c4b8a3d6e9"
down_revision: Union[str, None] = "a3f9c1e6b7d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "automation_activity_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=64),
            sa.ForeignKey("platform_organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("lead_name", sa.String(length=255), nullable=False),
        sa.Column("automation_name", sa.String(length=255), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_automation_activity_log_organization_id", "automation_activity_log", ["organization_id"]
    )
    op.create_index(
        "ix_automation_activity_log_lead_id", "automation_activity_log", ["lead_id"]
    )
    op.create_index(
        "ix_automation_activity_log_org_id_created_at",
        "automation_activity_log",
        ["organization_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_automation_activity_log_org_id_created_at", table_name="automation_activity_log")
    op.drop_index("ix_automation_activity_log_lead_id", table_name="automation_activity_log")
    op.drop_index("ix_automation_activity_log_organization_id", table_name="automation_activity_log")
    op.drop_table("automation_activity_log")
