"""add leads notes/next_action/next_action_due_at

Pure additive: three new nullable columns (no data loss on existing rows)
plus a composite index backing GET /leads/tasks (WHERE organization_id = ...
AND next_action_due_at IS NOT NULL ORDER BY next_action_due_at ASC).

owner_id is intentionally NOT part of this migration — see the follow-up
migration once lead ownership's identity source is settled (this codebase
has no `users` table; the real user identity is `platform_users`, keyed by
email, not a UUID id).

Revision ID: c7d4f2a8e1b6
Revises: b2e5a9d4c1f7
Create Date: 2026-09-02 00:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c7d4f2a8e1b6"
down_revision: Union[str, None] = "b2e5a9d4c1f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("leads", sa.Column("next_action", sa.Text(), nullable=True))
    op.add_column(
        "leads", sa.Column("next_action_due_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        "ix_leads_org_id_next_action_due_at", "leads", ["organization_id", "next_action_due_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_leads_org_id_next_action_due_at", table_name="leads")
    op.drop_column("leads", "next_action_due_at")
    op.drop_column("leads", "next_action")
    op.drop_column("leads", "notes")
