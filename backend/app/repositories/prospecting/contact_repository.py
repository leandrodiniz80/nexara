import uuid
from typing import Sequence

from sqlalchemy import select

from app.models.prospecting.contact import Contact
from app.repositories.base import BaseRepository


class ContactRepository(BaseRepository[Contact]):
    model = Contact

    async def list_by_company(self, company_id: uuid.UUID) -> Sequence[Contact]:
        stmt = select(Contact).where(
            Contact.company_id == company_id, Contact.deleted_at.is_(None)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
