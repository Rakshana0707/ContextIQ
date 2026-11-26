"""
SQLAlchemy engine / session management.

Provides:
- `engine`: the SQLAlchemy engine bound to DATABASE_URL
- `SessionLocal`: session factory
- `get_db`: FastAPI dependency that yields a request-scoped session
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine_kwargs = {"echo": settings.DB_ECHO}
if "sqlite" in settings.DATABASE_URL:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
    })

engine = create_engine(
    settings.DATABASE_URL,
    **engine_kwargs,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


def get_db() -> Generator:
    """FastAPI dependency: yields a DB session and guarantees it is closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
