from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_auth.user import PlatformUser
from app.models.platform_auth.user_organization import PlatformUserOrganization


async def list_organization_member_emails(db: AsyncSession, organization_id: str) -> list[str]:
    """Every user who belongs to organization_id. PlatformUser.organization_id
    alone is not the complete membership list: it's only a user's *primary*
    org (set at registration; create_or_replace_user() never inserts a
    PlatformUserOrganization row for it), while genuine additional
    memberships (add_user_to_organization()) live only in
    PlatformUserOrganization — neither table alone is complete, so this is
    the union of both, deduped by email.
    """
    primary_stmt = select(PlatformUser.email).where(PlatformUser.organization_id == organization_id)
    secondary_stmt = select(PlatformUserOrganization.user_email).where(
        PlatformUserOrganization.organization_id == organization_id
    )
    primary_emails = (await db.execute(primary_stmt)).scalars().all()
    secondary_emails = (await db.execute(secondary_stmt)).scalars().all()
    return sorted(set(primary_emails) | set(secondary_emails))
