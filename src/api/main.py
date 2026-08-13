"""FastAPI application entry point."""

from fastapi import FastAPI
from contextlib import asynccontextmanager

from src.utils.config import settings
from src.db.session import engine
from src.db.models import Base


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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "a1-ai-system",
        "version": "0.1.0",
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "A1 AI System is running",
        "docs": "/docs",
    }
