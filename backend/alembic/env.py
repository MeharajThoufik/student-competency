from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Arbitrary constant; serialises concurrent migrations when several Cloud Run instances start together.
MIGRATION_LOCK_ID = 7_220_001


def run_migrations_offline() -> None:
    context.configure(url=get_settings().database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = get_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    engine = create_engine(url)
    with engine.connect() as connection:
        is_pg = connection.dialect.name == "postgresql"
        if is_pg:
            connection.execute(text("SELECT pg_advisory_lock(:id)"), {"id": MIGRATION_LOCK_ID})
            connection.commit()
        try:
            context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
            connection.commit()
        finally:
            if is_pg:
                connection.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": MIGRATION_LOCK_ID})
                connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
