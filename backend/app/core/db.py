from functools import lru_cache

from sqlalchemy import Engine, create_engine, text

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine | None:
    url = get_settings().database_url
    if not url:
        return None
    return create_engine(url, pool_pre_ping=True, pool_size=5, connect_args={"connect_timeout": 3})


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
