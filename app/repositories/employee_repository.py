from typing import Any

# Repositories are the only code that queries MongoDB. The projection
# returns only the fields the app needs (and hides MongoDB's _id).
EMPLOYEE_PROJECTION = {"_id": 0, "employee_id": 1, "name": 1, "department": 1, "active": 1}


class EmployeeRepository:
    def __init__(self, database: Any) -> None:
        self.collection = database.employees

    async def get_by_id(self, employee_id: str) -> dict | None:
        # Exact match on employee_id; returns None when not found.
        return await self.collection.find_one({"employee_id": employee_id}, EMPLOYEE_PROJECTION)
