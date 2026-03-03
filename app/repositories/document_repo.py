from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document
from app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    def __init__(self, db: AsyncSession):
        super().__init__(Document, db)

    async def get_by_owner(self, owner_id: UUID, limit: int = 50, offset: int = 0) -> list[Document]:
        result = await self.db.execute(
            select(Document)
            .where(Document.owner_id == owner_id)
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_checksum(self, checksum: str, owner_id: UUID) -> Document | None:
        result = await self.db.execute(
            select(Document).where(
                Document.checksum == checksum,
                Document.owner_id == owner_id,
            )
        )
        return result.scalar_one_or_none()
