"""create user_notifications

Persistent counterpart to the toast messages a "notify" automation firing
has always returned in the HTTP response — this round's one justified new
table (per the user's own explicit "pode criar nova tabela (notifications)
-> JUSTIFICADO"). lead_id is nullable and not part of the literal field
list this round's spec gave, added so "click a notification to open its
lead" is actually implementable.

Revision ID: f8b3d6c1a4e7
Revises: e4f7b2c9a3d1
Create Date: 2026-09-02 00:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f8b3d6c1a4e7"
down_revision: Union[str, None] = "e4f7b2c9a3d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=64),
            sa.ForeignKey("platform_organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_email",
            sa.String(length=255),
            sa.ForeignKey("platform_users.email", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("read", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_user_notifications_org_user_created_at",
        "user_notifications",
        ["organization_id", "user_email", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_notifications_org_user_created_at", table_name="user_notifications")
    op.drop_table("user_notifications")
