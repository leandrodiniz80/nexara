"""create lead status history

Append-only audit trail of lead status transitions — every PATCH
/leads/{id}/status writes one row here alongside the lead's own update.
Separate migration (not folded into the leads-domain one): that migration
already ran in production, so it can't be edited anymore.

Revision ID: e7a2b9c4f1d8
Revises: c4d8f612a9e3
Create Date: 2026-09-03 00:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7a2b9c4f1d8"
down_revision: Union[str, None] = "c4d8f612a9e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lead_status_history",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lead_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.String(length=64),
            sa.ForeignKey("platform_organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_lead_status_history_lead_id", "lead_status_history", ["lead_id"])
    op.create_index(
        "ix_lead_status_history_organization_id", "lead_status_history", ["organization_id"]
    )


def downgrade() -> None:
    op.drop_table("lead_status_history")
