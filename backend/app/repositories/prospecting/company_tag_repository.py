import uuid

from sqlalchemy import select

from app.models.prospecting.company_tag import CompanyTag
from app.repositories.base import BaseRepository


class CompanyTagRepository(BaseRepository[CompanyTag]):
    model = CompanyTag

    async def get_by_company_and_tag(
        self, company_id: uuid.UUID, tag_id: uuid.UUID
    ) -> CompanyTag | None:
        stmt = select(CompanyTag).where(
            CompanyTag.company_id == company_id,
            CompanyTag.tag_id == tag_id,
            CompanyTag.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
