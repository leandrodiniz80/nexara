"""create platform auth domain

Fase 1 — persistence for PlatformAuth: users, organizations, genuine
many-to-many user/organization membership, sessions and per-organization
daily usage counters. None of this existed as real tables before —
PlatformAuth ran entirely on in-process dicts, and even its own
PostgresStorage fallback only ever wrote a single JSONB blob, never a
"sessions" bucket at all (PlatformAuth._persist() never included
self._sessions). This migration is the actual fix.

Revision ID: 3b8af1b3f7c4
Revises: 9a9d9f54336a
Create Date: 2026-08-17 00:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3b8af1b3f7c4"
down_revision: Union[str, None] = "9a9d9f54336a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------- platform_organizations ----------
    op.create_table(
        "platform_organizations",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("plan", sa.String(length=32), nullable=False, server_default="free"),
        sa.Column(
            "plan_history",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "retention_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "lead_states",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
        sa.Column("subscription_status", sa.String(length=32), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_platform_organizations_stripe_customer_id",
        "platform_organizations",
        ["stripe_customer_id"],
    )

    # ---------- platform_users ----------
    op.create_table(
        "platform_users",
        sa.Column("email", sa.String(length=255), primary_key=True),
        sa.Column("password_salt", sa.LargeBinary(), nullable=False),
        sa.Column("password_hash", sa.LargeBinary(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="user"),
        sa.Column(
            "permissions",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "organization_id",
            sa.String(length=64),
            sa.ForeignKey("platform_organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "organization_role", sa.String(length=32), nullable=False, server_default="member"
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_platform_users_organization_id", "platform_users", ["organization_id"])
    op.create_index("ix_platform_users_role", "platform_users", ["role"])

    # ---------- user_organizations (genuine many-to-many) ----------
    op.create_table(
        "user_organizations",
        sa.Column(
            "user_email",
            sa.String(length=255),
            sa.ForeignKey("platform_users.email", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "organization_id",
            sa.String(length=64),
            sa.ForeignKey("platform_organizations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="member"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_user_organizations_organization_id", "user_organizations", ["organization_id"]
    )

    # ---------- platform_sessions ----------
    op.create_table(
        "platform_sessions",
        sa.Column("token", sa.Text(), primary_key=True),
        sa.Column(
            "user_email",
            sa.String(length=255),
            sa.ForeignKey("platform_users.email", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.String(length=64),
            sa.ForeignKey("platform_organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("role", sa.String(length=32), nullable=True),
        sa.Column(
            "permissions",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_platform_sessions_user_email", "platform_sessions", ["user_email"])
    op.create_index("ix_platform_sessions_expires_at", "platform_sessions", ["expires_at"])

    # ---------- platform_usage ----------
    op.create_table(
        "platform_usage",
        sa.Column(
            "organization_id",
            sa.String(length=64),
            sa.ForeignKey("platform_organizations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("usage_date", sa.Date(), primary_key=True),
        sa.Column("requests_today", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("platform_usage")
    op.drop_table("platform_sessions")
    op.drop_table("user_organizations")
    op.drop_table("platform_users")
    op.drop_table("platform_organizations")
