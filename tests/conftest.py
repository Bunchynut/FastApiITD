import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from src.DataBase import Base, engine, engine_null_pull
from src.config import settings
from src.model import *

@pytest.fixture(autouse=True, scope='session')
async def async_main():
    assert settings.MODE


    async with engine_null_pull.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)