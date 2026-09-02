"""add leads org_id+created_at composite index

Pure additive index — no column/table changes, no contract change. Backs
the existing GET /leads query shape (WHERE organization_id = ... ORDER BY
created_at DESC): today's single-column ix_leads_org_id still filters
correctly, but Postgres has to sort the matched rows separately; once an
organization's lead count grows, this composite index lets it satisfy the
filter and the ordering from the index directly, no separate sort step.

Revision ID: a3f9c1e6b7d2
Revises: e7a2b9c4f1d8
Create Date: 2026-09-03 00:00:00

"""

from typing import Sequence, Union

from alembic import op

revision: str = "a3f9c1e6b7d2"
down_revision: Union[str, None] = "e7a2b9c4f1d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_leads_org_id_created_at", "leads", ["organization_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_leads_org_id_created_at", table_name="leads")
