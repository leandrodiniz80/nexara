from sqlalchemy import select

from app.models.prospecting.company import Company
from app.repositories.base import BaseRepository


class CompanyRepository(BaseRepository[Company]):
    model = Company

    async def get_by_cnpj(self, cnpj: str) -> Company | None:
        stmt = select(Company).where(Company.cnpj == cnpj, Company.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
