"""FastAPI application entry point."""

from fastapi import FastAPI
from contextlib import asynccontextmanager
from starlette.middleware.sessions import SessionMiddleware

from src.utils.config import settings
from src.db.session import engine
from src.db.models import Base
from src.api.dashboard import dashboard_router
from src.api.miniapp import miniapp_router
from src.api.admin import admin_router
from src.api.cards import cards_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup: create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown: dispose engine
    await engine.dispose()


app = FastAPI(
    title="A1 AI System API",
    description="AI-система управления строительной компанией ООО «А1»",
    version="0.1.0",
    lifespan=lifespan,
)

# Session middleware for admin auth
app.add_middleware(SessionMiddleware, secret_key="a1-system-secret-key-2026-secure")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "a1-ai-system",
        "version": "0.1.0",
    }


app.include_router(dashboard_router)
app.include_router(miniapp_router)
app.include_router(admin_router)
app.include_router(cards_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "A1 AI System is running",
        "docs": "/docs",
        "dashboard": "/dashboard",
    }
