"""FastAPI application entry point.

Run locally:
    .venv\\Scripts\\python.exe -m uvicorn app.main:app --reload --port 8000
Swagger UI:  http://localhost:8000/docs
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, classes, health, lectures, meetings
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.init_db import init_db

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
    init_db()
    logger.info("%s ready — API prefix '%s'", settings.app_name, settings.api_prefix)
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Backend for the Deep Learning-based AI Online Class & Meeting Assistant. "
        "Uploads a lecture recording (or transcript), transcribes it, classifies "
        "transcript segments with a Transformer, and generates notes, summaries, "
        "Q&A, announcements and action items."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Keeps unexpected errors JSON-shaped (and logged) instead of leaking HTML."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error while processing the request."},
    )


for router in (
    health.router,
    auth.router,
    classes.router,
    classes.inbox_router,
    classes.notes_router,
    classes.dashboard_router,
    lectures.router,
    meetings.router,
):
    app.include_router(router, prefix=settings.api_prefix)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "health": f"{settings.api_prefix}/health",
    }
