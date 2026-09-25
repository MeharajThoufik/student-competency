from collections.abc import Iterator
from functools import lru_cache

from fastapi import HTTPException, status
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine | None:
    url = get_settings().database_url
    if not url:
        return None
    # Small pool: db-f1-micro allows ~25 connections, shared by up to 3 Cloud Run instances.
    return create_engine(url, pool_pre_ping=True, pool_size=3, max_overflow=2)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session] | None:
    engine = get_engine()
    return sessionmaker(bind=engine, expire_on_commit=False) if engine else None


def get_db() -> Iterator[Session]:
    factory = get_sessionmaker()
    if factory is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database not configured")
    with factory() as session:
        yield session


def check_database() -> str:
    engine = get_engine()
    if engine is None:
        return "not_configured"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "unavailable"
