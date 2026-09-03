"""add leads enrichment fields

Pure additive: three new nullable columns (company_name, website,
enrichment_data JSONB) — the "mini-dossier" a lead gains automatically on
creation (Auto-enrich New Lead automation) or on demand (POST
/leads/{id}/enrich). No data loss, no existing column touched.

Revision ID: c3f6a9d2e5b8
Revises: a2d5e8f3c6b9
Create Date: 2026-09-02 00:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3f6a9d2e5b8"
down_revision: Union[str, None] = "a2d5e8f3c6b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("company_name", sa.String(length=255), nullable=True))
    op.add_column("leads", sa.Column("website", sa.String(length=255), nullable=True))
    op.add_column("leads", sa.Column("enrichment_data", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "enrichment_data")
    op.drop_column("leads", "website")
    op.drop_column("leads", "company_name")
