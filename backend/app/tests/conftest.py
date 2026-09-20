"""Shared pytest configuration: an isolated async DB session.

Against PostgreSQL (the compose environment) each test session uses its own
schema and rolls back; locally the suite can run with a file-backed
aiosqlite database via ``DATABASE_URL`` so the pure-persistence tests remain
runnable without a database server.
"""

from __future__ import annotations

import asyncio
import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.persistence.models import Base

TEST_URL = os.environ.get(
    "TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture()
async def session():
    engine = create_async_engine(TEST_URL, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
