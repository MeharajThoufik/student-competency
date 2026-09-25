from fastapi import APIRouter

from app.core.config import get_settings
from app.core.db import check_database

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "version": settings.version,
        "environment": settings.environment,
        "database": check_database(),
    }
