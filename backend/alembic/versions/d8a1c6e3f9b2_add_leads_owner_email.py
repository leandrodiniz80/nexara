"""add leads owner_email

Real FK to platform_users.email (this codebase's actual user identity —
there is no users.id UUID table) rather than an unenforced UUID placeholder
like AuditMixin's created_by/updated_by. ON DELETE SET NULL: a deleted user
un-assigns their leads rather than blocking the delete or cascading it away.

Pure additive: one new nullable column, no data loss on existing rows.

Revision ID: d8a1c6e3f9b2
Revises: c7d4f2a8e1b6
Create Date: 2026-09-02 00:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d8a1c6e3f9b2"
down_revision: Union[str, None] = "c7d4f2a8e1b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("owner_email", sa.String(length=255), nullable=True))
    op.create_foreign_key(
        "fk_leads_owner_email_platform_users",
        "leads",
        "platform_users",
        ["owner_email"],
        ["email"],
        ondelete="SET NULL",
    )
    op.create_index("ix_leads_owner_email", "leads", ["owner_email"])


def downgrade() -> None:
    op.drop_index("ix_leads_owner_email", table_name="leads")
    op.drop_constraint("fk_leads_owner_email_platform_users", "leads", type_="foreignkey")
    op.drop_column("leads", "owner_email")
