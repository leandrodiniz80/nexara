"""create lead_activity_log

New append-only table for manual, non-automation lead events (owner
reassignment, notes/next_action edits, task completions) — the one new
table this round's timeline unification needs. LeadStatusHistory and
AutomationActivityLog are reused as-is (no schema change to either): neither
fits these event shapes without overloading columns that already have a
narrower, established meaning.

Revision ID: e4f7b2c9a3d1
Revises: d8a1c6e3f9b2
Create Date: 2026-09-02 00:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e4f7b2c9a3d1"
down_revision: Union[str, None] = "d8a1c6e3f9b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lead_activity_log",
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
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_lead_activity_log_organization_id", "lead_activity_log", ["organization_id"])
    op.create_index(
        "ix_lead_activity_log_lead_id_created_at", "lead_activity_log", ["lead_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_lead_activity_log_lead_id_created_at", table_name="lead_activity_log")
    op.drop_index("ix_lead_activity_log_organization_id", table_name="lead_activity_log")
    op.drop_table("lead_activity_log")
