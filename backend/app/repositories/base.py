import uuid
from datetime import datetime, timezone
from typing import Generic, Sequence, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


def actor_kwargs(updated_by: uuid.UUID | None) -> dict:
    """`BaseRepository.update()` does an unconditional setattr for every kwarg it
    receives, so a bare `updated_by=None` would silently wipe out a previously recorded
    actor. Engines should spread this in rather than passing `updated_by=` directly."""
    return {"updated_by": updated_by} if updated_by is not None else {}


class BaseRepository(Generic[ModelType]):
    """Generic async CRUD repository with soft-delete built in.

    Subclasses must set `model`. Domain-specific query methods (lookups,
    filters) belong in the subclass, not here.
    """

    model: type[ModelType]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self, id: uuid.UUID, *, include_deleted: bool = False
    ) -> ModelType | None:
        stmt = select(self.model).where(self.model.id == id)
        if not include_deleted:
            stmt = stmt.where(self.model.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self, *, limit: int = 50, offset: int = 0, include_deleted: bool = False
    ) -> Sequence[ModelType]:
        stmt = select(self.model).limit(limit).offset(offset).order_by(self.model.created_at.desc())
        if not include_deleted:
            stmt = stmt.where(self.model.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, **attrs) -> ModelType:
        instance = self.model(**attrs)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def update(self, instance: ModelType, **attrs) -> ModelType:
        for field, value in attrs.items():
            setattr(instance, field, value)
        await self.session.flush()
        return instance

    async def soft_delete(self, instance: ModelType, *, deleted_by: uuid.UUID | None = None) -> ModelType:
        instance.deleted_at = datetime.now(timezone.utc)
        if deleted_by is not None:
            instance.updated_by = deleted_by
        await self.session.flush()
        return instance

    async def restore(self, instance: ModelType) -> ModelType:
        instance.deleted_at = None
        await self.session.flush()
        return instance
