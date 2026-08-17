from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def _sync_url(database_url: str) -> str:
    """`settings.DATABASE_URL` is the async form `AsyncSessionLocal` needs
    (`postgresql+asyncpg://...`) — `AuthRepository` is deliberately
    synchronous (Fase 1's `PlatformAuth` stays 100% sync, see
    `auth_repository.py`), which needs the `psycopg2` driver instead.
    """
    if "+asyncpg" in database_url:
        return database_url.replace("+asyncpg", "+psycopg2")

    return database_url


sync_engine = create_engine(_sync_url(settings.DATABASE_URL), pool_pre_ping=True)

SyncSessionLocal: sessionmaker[Session] = sessionmaker(bind=sync_engine, expire_on_commit=False)
