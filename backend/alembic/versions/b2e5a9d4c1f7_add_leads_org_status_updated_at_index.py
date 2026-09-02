"""add leads org_id+status+updated_at composite index

Pure additive index — backs the new GET /leads/attention query shape
(WHERE organization_id = ... AND status IN (...) ORDER BY updated_at ASC),
same rationale as ix_leads_org_id_created_at: no column/table change, no
contract change.

Revision ID: b2e5a9d4c1f7
Revises: f1c4b8a3d6e9
Create Date: 2026-09-02 00:00:00

"""

from typing import Sequence, Union

from alembic import op

revision: str = "b2e5a9d4c1f7"
down_revision: Union[str, None] = "f1c4b8a3d6e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_leads_org_id_status_updated_at", "leads", ["organization_id", "status", "updated_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_leads_org_id_status_updated_at", table_name="leads")
