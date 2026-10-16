"""Application entry point."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.config import APP_ENV
from app.database import Base, engine
from app import models  # noqa: F401 - registers SQLAlchemy models with Base metadata
from app.ai.router import router as ai_router
from app.routers.students import router as students_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Create tables on normal startup; tests use their own isolated database."""
    if APP_ENV != "test":
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Students Database CRUD API",
    description=(
        "A beginner-friendly FastAPI backend for student records, with SQLite persistence "
        "and an optional local Ollama question-answering endpoint."
    ),
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(students_router)
app.include_router(ai_router)


@app.get("/health", tags=["System"], summary="Check API health")
def health() -> dict[str, str]:
    """Return a simple health status."""
    return {"status": "ok"}
