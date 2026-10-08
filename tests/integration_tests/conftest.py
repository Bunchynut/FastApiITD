"""Real PostgreSQL tests in an owned schema, rolled back after every test."""

import json
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from httpx import ASGITransport, AsyncClient
from sqlalchemy import NullPool, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.DataBase import Base
from src.FastApiOb import app
from src.Schemas.Schemas import HotelPost
from src.Schemas.rooms import RoomsTestMain
from src.api.Dependencied import get_db
from src.config import settings
from src.model import *  # noqa: F403 -- register every table in metadata
from src.utils.db_manager import DBManager

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_engine():
    if settings.MODE != "TEST":
        pytest.fail("Integration tests require MODE=TEST; refusing database access.")
    # Only this unpredictable, owned schema is created and removed.
    schema = f"pytest_{uuid4().hex}"
    engine = create_async_engine(
        settings.DB_URL,
        poolclass=NullPool,
        connect_args={"server_settings": {"search_path": schema}},
    )
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.run_sync(Base.metadata.create_all)
        try:
            yield engine
        finally:
            async with engine.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    finally:
        await engine.dispose()


@pytest.fixture
async def test_session_factory(test_engine):
    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        factory = async_sessionmaker(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            async with DBManager(factory) as seed_db:
                hotels = json.loads(
                    (PROJECT_ROOT / "tests/mock_hotels.json").read_text(
                        encoding="utf-8"
                    )
                )
                rooms = json.loads(
                    (PROJECT_ROOT / "tests/mock_rooms.json").read_text(encoding="utf-8")
                )
                # Seed room data references hotel IDs; sequences survive rollback.
                await connection.execute(
                    text("ALTER SEQUENCE hotels_id_seq RESTART WITH 1")
                )
                await connection.execute(
                    text("ALTER SEQUENCE rooms_id_seq RESTART WITH 1")
                )
                await seed_db.hotels.add_bulk(
                    [HotelPost.model_validate(item) for item in hotels]
                )
                await seed_db.rooms.add_bulk(
                    [RoomsTestMain.model_validate(item) for item in rooms]
                )
                await seed_db.commit()
            yield factory
        finally:
            await transaction.rollback()


@pytest.fixture
async def db(test_session_factory):
    async with DBManager(test_session_factory) as manager:
        yield manager


@pytest.fixture
async def ac(test_session_factory):
    async def override_db():
        async with DBManager(test_session_factory) as manager:
            yield manager

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_db
    FastAPICache.reset()
    FastAPICache.init(InMemoryBackend(), prefix=f"test-{uuid4().hex}")
    try:
        # HTTP exercises real routes without starting Redis/Celery lifespan.
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        FastAPICache.reset()


@pytest.fixture
async def register_user(ac, user_data):
    response = await ac.post("/users/auth", json=user_data)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
async def auth_ac(ac, register_user, user_data):
    response = await ac.post(
        "/users/login",
        json={"email": user_data["email"], "password": user_data["password"]},
    )
    assert response.status_code == 200, response.text
    assert ac.cookies.get("access_token") == response.json()["access_token"]
    return ac
