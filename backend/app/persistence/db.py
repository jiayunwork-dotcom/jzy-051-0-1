"""SQLAlchemy engine/session management.

* In the docker-compose deployment ``DATABASE_URL`` points at the
  PostgreSQL 16 service (asyncpg driver).
* When the variable is unset (local development / unit runs) a file-backed
  SQLite database is used instead, so the whole suite runs without a
  database server — the ORM models only use portable column types.

The engine is created lazily so merely importing the app never requires the
async driver to be installed.
"""

from __future__ import annotations

import os
import tempfile

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def _default_url() -> str:
    explicit = os.environ.get("DATABASE_URL")
    if explicit:
        return explicit
    path = os.path.join(tempfile.gettempdir(), "latex_editor_dev.db")
    return f"sqlite+aiosqlite:///{path}"


_engine = None
_SessionLocal = None


def _ensure_engine():
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_async_engine(_default_url(), echo=False, future=True)
        _SessionLocal = async_sessionmaker(_engine, expire_on_commit=False,
                                           class_=AsyncSession)
    return _engine, _SessionLocal


async def init_models() -> None:
    from .models import Base
    engine, _ = _ensure_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """FastAPI dependency."""
    _, maker = _ensure_engine()
    async with maker() as session:
        yield session
