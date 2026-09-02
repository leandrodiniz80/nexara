"""create leads domain

Persists the Leads feature (frontend/src/lib/mocks/leads.ts +
lib/services/leads-service.ts) and its automation engine, both previously
localStorage-only. Two tables: `leads` and `automations`, both scoped to
`platform_organizations` — no Mission/Campaign coupling, see Lead's own
docstring for why this is intentionally separate from the Prospect
aggregate.

Revision ID: c4d8f612a9e3
Revises: 3b8af1b3f7c4
Create Date: 2026-09-02 00:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4d8f612a9e3"
down_revision: Union[str, None] = "3b8af1b3f7c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------- leads ----------
    op.create_table(
        "leads",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=64),
            sa.ForeignKey("platform_organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="new"),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("status IN ('new','contacted','converted','lost')", name="ck_leads_status"),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_leads_score"),
    )
    op.create_index("ix_leads_org_id", "leads", ["organization_id"])
    op.create_index("ix_leads_email", "leads", ["email"])
    op.create_index("ix_leads_status", "leads", ["status"])

    # ---------- automations ----------
    op.create_table(
        "automations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=64),
            sa.ForeignKey("platform_organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "trigger_type",
            sa.String(length=32),
            nullable=False,
            server_default="lead_status_changed",
        ),
        sa.Column("trigger_from", sa.String(length=32), nullable=True),
        sa.Column("trigger_to", sa.String(length=32), nullable=True),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        # Backs seed_default_automations()'s ON CONFLICT DO NOTHING — without
        # this, two concurrent first-ever GET /automations for the same new
        # org could both see an empty list and both insert, duplicating rows.
        sa.UniqueConstraint("organization_id", "name", name="uq_automations_org_name"),
    )
    op.create_index("ix_automations_org_id", "automations", ["organization_id"])
    op.create_index("ix_automations_active", "automations", ["active"])


def downgrade() -> None:
    op.drop_table("automations")
    op.drop_table("leads")
