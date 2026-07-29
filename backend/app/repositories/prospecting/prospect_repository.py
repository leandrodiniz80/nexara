import uuid
from typing import Sequence

from sqlalchemy import or_, select

from app.models.prospecting.company import Company
from app.models.prospecting.enums import ProspectPriority, ProspectStage, ProspectStatus, ProspectTemperature
from app.models.prospecting.prospect import Prospect
from app.repositories.base import BaseRepository


class ProspectRepository(BaseRepository[Prospect]):
    model = Prospect

    async def list_pipeline(
        self, *, owner_id: uuid.UUID | None = None, limit: int = 50, offset: int = 0
    ) -> Sequence[Prospect]:
        """Open opportunities only (excludes WON/LOST/DISQUALIFIED), highest priority first."""
        stmt = (
            select(Prospect)
            .where(Prospect.deleted_at.is_(None), Prospect.status == ProspectStatus.OPEN)
            .order_by(Prospect.priority.desc(), Prospect.created_at.asc())
        )
        if owner_id is not None:
            stmt = stmt.where(Prospect.owner_id == owner_id)
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_by_stage(
        self, stage: ProspectStage, *, limit: int = 50, offset: int = 0
    ) -> Sequence[Prospect]:
        stmt = (
            select(Prospect)
            .where(Prospect.deleted_at.is_(None), Prospect.current_stage == stage)
            .order_by(Prospect.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_by_campaign(
        self, campaign_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> Sequence[Prospect]:
        stmt = (
            select(Prospect)
            .where(Prospect.deleted_at.is_(None), Prospect.campaign_id == campaign_id)
            .order_by(Prospect.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_by_owner(
        self, owner_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> Sequence[Prospect]:
        stmt = (
            select(Prospect)
            .where(Prospect.deleted_at.is_(None), Prospect.owner_id == owner_id)
            .order_by(Prospect.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_by_mission(self, mission_id: uuid.UUID) -> Sequence[Prospect]:
        """No pagination: MissionEngine needs the full set to compute metrics/progress."""
        stmt = select(Prospect).where(
            Prospect.deleted_at.is_(None), Prospect.mission_id == mission_id
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def search(
        self,
        *,
        query: str | None = None,
        stage: ProspectStage | None = None,
        status: ProspectStatus | None = None,
        temperature: ProspectTemperature | None = None,
        priority: ProspectPriority | None = None,
        campaign_id: uuid.UUID | None = None,
        owner_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Prospect]:
        """Flexible pipeline search: free-text over company name/notes plus exact filters."""
        stmt = select(Prospect).where(Prospect.deleted_at.is_(None))

        if query:
            stmt = stmt.join(Company, Company.id == Prospect.company_id).where(
                or_(
                    Company.legal_name.ilike(f"%{query}%"),
                    Company.trade_name.ilike(f"%{query}%"),
                    Prospect.notes.ilike(f"%{query}%"),
                )
            )
        if stage is not None:
            stmt = stmt.where(Prospect.current_stage == stage)
        if status is not None:
            stmt = stmt.where(Prospect.status == status)
        if temperature is not None:
            stmt = stmt.where(Prospect.temperature == temperature)
        if priority is not None:
            stmt = stmt.where(Prospect.priority == priority)
        if campaign_id is not None:
            stmt = stmt.where(Prospect.campaign_id == campaign_id)
        if owner_id is not None:
            stmt = stmt.where(Prospect.owner_id == owner_id)

        stmt = stmt.order_by(Prospect.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return result.scalars().all()
