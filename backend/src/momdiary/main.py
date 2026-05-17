"""FastAPI application factory and lifespan."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from momdiary.db.engine import dispose_engine
from momdiary.observability.logging import configure_logging, get_logger
from momdiary.observability.middleware import CorrelationIdMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    logger.info("app.startup", title=app.title, version=app.version)
    try:
        yield
    finally:
        logger.info("app.shutdown")
        await dispose_engine()


def create_app() -> FastAPI:
    """Application factory used by uvicorn and the contract tests."""
    app = FastAPI(
        title="MomDiary Baby Tracker Backend",
        version="0.1.0",
        lifespan=_lifespan,
    )
    app.add_middleware(CorrelationIdMiddleware)

    # Routers are registered lazily by their respective phases to keep this
    # module a stable composition root.
    from momdiary.api import appointments, entries, feeds, poops, sleeps

    app.include_router(entries.router, prefix="/v1")
    app.include_router(feeds.router, prefix="/v1")
    app.include_router(sleeps.router, prefix="/v1")
    app.include_router(poops.router, prefix="/v1")
    app.include_router(appointments.router, prefix="/v1")
    logger.info("app.routers_registered", count=5)
    return app


app = create_app()
