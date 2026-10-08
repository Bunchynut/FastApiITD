from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend

from src import FastApiOb as application
from src.connectors import redis_connectors
from src.connectors.redis_connectors import RedisManager


@pytest.fixture
def redis_client():
    return AsyncMock()


async def test_redis_connect_uses_configured_host_and_port(monkeypatch, redis_client):
    constructor = AsyncMock(return_value=redis_client)
    monkeypatch.setattr(redis_connectors.redis, "Redis", constructor)
    manager = RedisManager(host="test-redis", port=6380)
    assert manager.redis is None
    await manager.connect()
    constructor.assert_awaited_once_with(host="test-redis", port=6380)
    assert manager.redis is redis_client


@pytest.mark.parametrize("expire", [None, 60])
async def test_redis_set_passes_optional_expiry(redis_client, expire):
    manager = RedisManager(host="test-redis", port=6380)
    manager.redis = redis_client
    await manager.set("key", "value", expire=expire)
    expected = {} if expire is None else {"ex": 60}
    redis_client.set.assert_awaited_once_with("key", "value", **expected)


async def test_redis_get_returns_value(redis_client):
    manager = RedisManager(host="test-redis", port=6380)
    manager.redis = redis_client
    redis_client.get.return_value = b"cached value"
    assert await manager.get("key") == b"cached value"
    redis_client.get.assert_awaited_once_with("key")


async def test_redis_delete_and_close(redis_client):
    manager = RedisManager(host="test-redis", port=6380)
    manager.redis = redis_client
    await manager.delete("key")
    await manager.close()
    redis_client.delete.assert_awaited_once_with("key")
    redis_client.close.assert_awaited_once_with()


async def test_redis_close_without_connection():
    await RedisManager(host="test-redis", port=6380).close()


async def test_redis_operation_propagates_failure(redis_client):
    manager = RedisManager(host="test-redis", port=6380)
    manager.redis = redis_client
    error = ConnectionError("redis unavailable")
    redis_client.get.side_effect = error
    with pytest.raises(ConnectionError) as caught:
        await manager.get("key")
    assert caught.value is error


@pytest.fixture
def lifespan_manager(monkeypatch):
    manager = SimpleNamespace(connect=AsyncMock(), close=AsyncMock(), redis=AsyncMock())
    monkeypatch.setattr(application, "redis_manager", manager)
    FastAPICache.reset()
    yield manager
    FastAPICache.reset()


async def test_lifespan_connects_initializes_cache_and_closes(lifespan_manager):
    async with application.lifespan(application.app):
        lifespan_manager.connect.assert_awaited_once_with()
        lifespan_manager.close.assert_not_awaited()
        assert isinstance(FastAPICache.get_backend(), RedisBackend)
        assert FastAPICache.get_prefix() == "fastapi-cache"
    lifespan_manager.close.assert_awaited_once_with()


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="lifespan has no finally block, so Redis stays open when the app body raises",
)
async def test_lifespan_closes_connection_when_body_raises(lifespan_manager):
    error = RuntimeError("application failed")
    with pytest.raises(RuntimeError) as caught:
        async with application.lifespan(application.app):
            raise error
    assert caught.value is error
    lifespan_manager.close.assert_awaited_once_with()


async def test_docs_and_openapi_are_available_without_external_services():
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=application.app), base_url="http://test"
    ) as client:
        docs = await client.get("/docs")
        schema = await client.get("/openapi.json")
    assert docs.status_code == 200
    assert "/openapi.json" in docs.text
    assert schema.status_code == 200
    assert {
        "/users/auth",
        "/hotels",
        "/rooms",
        "/booking",
        "/facilities/",
        "/images",
    } <= set(schema.json()["paths"])
