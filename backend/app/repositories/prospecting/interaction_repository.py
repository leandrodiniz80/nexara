import uuid
from typing import Sequence

from sqlalchemy import select

from app.models.prospecting.interaction import Interaction
from app.repositories.base import BaseRepository


class InteractionRepository(BaseRepository[Interaction]):
    model = Interaction

    async def list_by_prospect(self, prospect_id: uuid.UUID) -> Sequence[Interaction]:
        stmt = (
            select(Interaction)
            .where(Interaction.prospect_id == prospect_id, Interaction.deleted_at.is_(None))
            .order_by(Interaction.occurred_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
