"""add workday focus fields

Pure additive: three new nullable/defaulted columns on leads (in_focus,
focused_at, focused_by_email) backing the "one lead in focus per user"
workday-mode lock, plus two new nullable columns on lead_activity_log
(user_email, duration_seconds) so a task_completed entry can attribute
itself to a user and record how long the lead sat in focus. No data loss,
no existing column touched.

Revision ID: a2d5e8f3c6b9
Revises: f8b3d6c1a4e7
Create Date: 2026-09-02 00:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a2d5e8f3c6b9"
down_revision: Union[str, None] = "f8b3d6c1a4e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("in_focus", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("leads", sa.Column("focused_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("leads", sa.Column("focused_by_email", sa.String(length=255), nullable=True))
    op.create_foreign_key(
        "fk_leads_focused_by_email_platform_users",
        "leads",
        "platform_users",
        ["focused_by_email"],
        ["email"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_leads_org_id_focused_by_email", "leads", ["organization_id", "focused_by_email"]
    )

    op.add_column("lead_activity_log", sa.Column("user_email", sa.String(length=255), nullable=True))
    op.add_column("lead_activity_log", sa.Column("duration_seconds", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_lead_activity_log_user_email_platform_users",
        "lead_activity_log",
        "platform_users",
        ["user_email"],
        ["email"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_lead_activity_log_user_email_platform_users", "lead_activity_log", type_="foreignkey"
    )
    op.drop_column("lead_activity_log", "duration_seconds")
    op.drop_column("lead_activity_log", "user_email")

    op.drop_index("ix_leads_org_id_focused_by_email", table_name="leads")
    op.drop_constraint("fk_leads_focused_by_email_platform_users", "leads", type_="foreignkey")
    op.drop_column("leads", "focused_by_email")
    op.drop_column("leads", "focused_at")
    op.drop_column("leads", "in_focus")
