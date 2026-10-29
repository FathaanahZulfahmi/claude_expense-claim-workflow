from typing import Any

from pymongo import AsyncMongoClient

from app.config import get_settings

# This module owns the MongoDB connection. Routes never create their own
# client; they ask for the shared database and pass it to repositories,
# which are the only code that queries it.
_client: AsyncMongoClient | None = None
_database: Any | None = None


# Called once at application startup (see lifespan in main.py).
async def connect_to_database() -> None:
    global _client, _database

    if _client is not None:
        return  # Already connected

    settings = get_settings()
    # Reveal the connection string only here, where it is needed.
    client = AsyncMongoClient(settings.mongodb_uri.get_secret_value())

    try:
        # Fail at startup (not mid-request) if MongoDB is unreachable.
        await client.admin.command("ping")
    except Exception:
        await client.close()
        raise

    _client = client
    _database = _client[settings.mongodb_database]


# Used by routes to get the shared database handle.
def get_database() -> Any:
    if _database is None:
        raise RuntimeError("Database connection is not established. Call connect_to_database() first.")
    return _database


# Called once at application shutdown (see lifespan in main.py).
async def close_database() -> None:
    global _client, _database

    if _client is not None:
        await _client.close()
        _client = None
        _database = None
