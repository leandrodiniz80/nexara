from sqlalchemy import select

from app.models.prospecting.email_template import EmailTemplate
from app.repositories.base import BaseRepository


class EmailTemplateRepository(BaseRepository[EmailTemplate]):
    model = EmailTemplate

    async def get_by_name(self, name: str) -> EmailTemplate | None:
        stmt = select(EmailTemplate).where(
            EmailTemplate.name == name, EmailTemplate.deleted_at.is_(None)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
