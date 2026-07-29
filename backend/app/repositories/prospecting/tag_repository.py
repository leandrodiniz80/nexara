from sqlalchemy import select

from app.models.prospecting.tag import Tag
from app.repositories.base import BaseRepository


class TagRepository(BaseRepository[Tag]):
    model = Tag

    async def get_by_name(self, name: str) -> Tag | None:
        stmt = select(Tag).where(Tag.name == name, Tag.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
