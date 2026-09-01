import asyncio
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.db import Base
from api.dependencies import get_db_session
from api.heal import create_app
from api.models import Site

# Tests run against in-memory SQLite so the suite needs no MySQL or InfluxDB.
TEST_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(TEST_URL)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client(session) -> AsyncIterator[AsyncClient]:
    """Api-component client with the database dependency pointed at SQLite.

    The api service never starts a scheduler, and lifespan is not run, so no
    external service is touched.
    """
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def site(session) -> Site:
    from api.cruds import sites as crud

    return await crud.create(session, {"name": "ArvanCloud", "fqdn": "arvancloud.ir"})
