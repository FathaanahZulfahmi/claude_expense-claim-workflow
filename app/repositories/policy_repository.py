from typing import Any

POLICY_PROJECTION = {"_id": 0, "category": 1, "max_amount": 1, "currency": 1}


class PolicyRepository:
    def __init__(self, database: Any) -> None:
        self.collection = database.expense_policies

    async def get_by_category(self, category: str) -> dict | None:
        # Returns None when no policy exists for this category.
        return await self.collection.find_one({"category": category}, POLICY_PROJECTION)
