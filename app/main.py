from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.database import close_database, connect_to_database
from app.routes import claims

# Load settings once at import time (fails early if a required setting is missing).
settings = get_settings()


# Everything before `yield` runs on startup; everything after runs on shutdown.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Open the shared MongoDB connection once, not on every request.
    await connect_to_database()
    try:
        yield
    finally:
        await close_database()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.include_router(claims.router)


@app.get("/health")
def health() -> dict:
    # Simple liveness check: proves the server is running. No AI involved.
    return {"status": "ok", "app": settings.app_name}
