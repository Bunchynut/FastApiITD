import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine

from src.DataBase import Base, engine, engine_null_pull
from src.FastApiOb import app
from src.config import settings
from src.model import *


@pytest.fixture(scope="session",autouse=True)
def check_test_mode():
    assert settings.MODE == 'TEST'

@pytest.fixture(autouse=True, scope='session')
async def async_main(check_test_mode):
    async with engine_null_pull.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture(autouse=True, scope='function')
async def register_user():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            '/auth/register',
            json={
                'email': 'reg@reg.com',
                'password': '12345',
            }
        )