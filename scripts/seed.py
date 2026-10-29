"""Employees and expense policies into MongoDB.
"""

import asyncio

from app.database import close_database, connect_to_database, get_database

# Who is allowed to submit claims. E003 is inactive so we can demo a rejection.
EMPLOYEES = [
    {"employee_id": "E001", "name": "Aisyah Rahman", "department": "Finance", "active": True},
    {"employee_id": "E002", "name": "Daniel Tan", "department": "Sales", "active": True},
    {"employee_id": "E003", "name": "Kumar Selvam", "department": "IT", "active": False},
]

# Company policy: the maximum amount per claim for each category (in MYR).
# The APPLICATION enforces these limits; Claude never sees or decides them.
# "other" has a limit of 0, so every "other" claim goes to human review.
POLICIES = [
    {"category": "travel", "max_amount": 500.00, "currency": "MYR"},
    {"category": "meals", "max_amount": 100.00, "currency": "MYR"},
    {"category": "accommodation", "max_amount": 400.00, "currency": "MYR"},
    {"category": "office_supplies", "max_amount": 200.00, "currency": "MYR"},
    {"category": "other", "max_amount": 0.00, "currency": "MYR"},
]


async def seed() -> None:
    await connect_to_database()
    try:
        db = get_database()

        # Unique indexes stop duplicate IDs / categories at the database level.
        await db.employees.create_index("employee_id", unique=True)
        await db.expense_policies.create_index("category", unique=True)
        await db.claims.create_index("claim_id", unique=True)

        for employee in EMPLOYEES:
            await db.employees.replace_one(
                {"employee_id": employee["employee_id"]}, employee, upsert=True
            )

        for policy in POLICIES:
            await db.expense_policies.replace_one(
                {"category": policy["category"]}, policy, upsert=True
            )

        print(f"employees:        {await db.employees.count_documents({})}")
        print(f"expense_policies: {await db.expense_policies.count_documents({})}")
        print(f"claims:           {await db.claims.count_documents({})}")
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(seed())
