import json
from unittest import mock

mock.patch('fastapi_cache.decorator.cache', lambda *args, **kwargs: lambda f: f).start()

import pytest
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine

from src.DataBase import Base, engine, engine_null_pull, async_session_maker_null_pull
from src.FastApiOb import app
from src.Schemas.Schemas import HotelPost
from src.Schemas.rooms import RoomsAdd, RoomsTestMain
from src.api.Dependencied import get_db
from src.config import settings
from src.model import *
from src.utils.db_manager import DBManager



@pytest.fixture(scope="session",autouse=True)
def check_test_mode():
    assert settings.MODE == 'TEST'


@pytest.fixture(scope='function')
async def db():
    async with DBManager(session_factory=async_session_maker_null_pull) as db:
        yield db



@pytest.fixture(autouse=True, scope='session')
async def async_main(check_test_mode):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    with open('tests/mock_hotels.json', encoding='utf-8') as hotels_file:
        hotels = json.load(hotels_file)
    hotels = [HotelPost.model_validate(hotel) for hotel in hotels]
    with open('tests/mock_rooms.json', encoding='utf-8') as rooms_file:
        rooms = json.load(rooms_file)
    rooms = [RoomsTestMain.model_validate(room) for room in rooms]

    async with DBManager(session_factory=async_session_maker_null_pull) as db_:
        await db_.hotels.add_bulk(hotels)
        await db_.rooms.add_bulk(rooms)
        await db_.commit()


@pytest.fixture(scope='session',autouse=True)
async def ac():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture()
async def register_user(ac):
    response = await ac.post(
         '/users/auth',
        json={
            "email": "user@example.com",
            "password": "string",
            "number": "+79999999999",
            "first_name": "string",
            "second_name": "string",
            "sex": "male"
        }
    )

    assert response.status_code in (200, 201), response.text

    return response.json()
