from typing import Any

from app.schemas.claim import ClaimResult


class ClaimRepository:
    def __init__(self, database: Any) -> None:
        self.collection = database.claims

    async def insert(self, claim: ClaimResult) -> None:
        # mode="json" turns enums and dates into plain strings MongoDB can
        # store. created_at stays a real datetime so it can be sorted on.
        document = claim.model_dump(mode="json")
        document["created_at"] = claim.created_at
        await self.collection.insert_one(document)
