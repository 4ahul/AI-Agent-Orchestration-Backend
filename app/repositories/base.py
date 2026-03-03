"""Generic base repository — avoids N+1 and raw query duplication."""
from typing import Any, Generic, Type, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db

    async def get(self, id: UUID) -> ModelType | None:
        result = await self.db.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[ModelType]:
        result = await self.db.execute(select(self.model).limit(limit).offset(offset))
        return list(result.scalars().all())

    async def create(self, obj: ModelType) -> ModelType:
        self.db.add(obj)
        await self.db.flush()  # Get DB-generated fields without committing
        await self.db.refresh(obj)
        return obj

    async def delete(self, id: UUID) -> bool:
        obj = await self.get(id)
        if obj:
            await self.db.delete(obj)
            return True
        return False
