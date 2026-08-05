"""
Health check endpoint. This is the one thing v0.1 needs to prove: the
service is built, deployable, and reachable — before any real logic exists.
"""
from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()


@router.get("/health")
def health_check() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
    }
