"""
v0.1 — Skeleton + deploy pipeline.

This app intentionally does nothing but prove the deployment path works:
FastAPI app -> Docker -> docker-compose -> (later) hosted platform.
Real endpoints (ingest, spend) arrive in v0.3 and v0.6.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import health
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.environment)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s in %s environment", settings.app_name, settings.environment)
    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
