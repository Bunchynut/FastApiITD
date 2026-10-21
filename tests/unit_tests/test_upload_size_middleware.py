import pytest

from src.middleware import ImageUploadSizeLimitMiddleware


class _WeakEnvelope(dict):
    __slots__ = ("__weakref__",)


@pytest.mark.asyncio
async def test_image_upload_middleware_rejects_oversized_streamed_body():
    app_called = False
    consumed = []
    messages = []
    incoming = iter(
        [
            {"type": "http.request", "body": b"123", "more_body": True},
            {"type": "http.request", "body": b"456", "more_body": False},
        ]
    )

    async def app(scope, receive, send):
        nonlocal app_called
        app_called = True
        while True:
            message = await receive()
            consumed.append(message.get("body", b""))
            if not message.get("more_body", False):
                break

    async def receive():
        return next(incoming)

    async def send(message):
        messages.append(message)

    middleware = ImageUploadSizeLimitMiddleware(app, max_bytes=5)
    await middleware(
        {"type": "http", "method": "POST", "path": "/images", "headers": []},
        receive,
        send,
    )

    assert not app_called
    assert consumed == []
    assert [message["status"] for message in messages if message["type"] == "http.response.start"] == [413]


@pytest.mark.asyncio
async def test_image_upload_middleware_rejects_large_content_length_early():
    app_called = False
    receive_called = False
    messages = []

    async def app(scope, receive, send):
        nonlocal app_called
        app_called = True

    async def receive():
        nonlocal receive_called
        receive_called = True
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    middleware = ImageUploadSizeLimitMiddleware(app, max_bytes=5)
    await middleware(
        {
            "type": "http",
            "method": "POST",
            "path": "/images",
            "headers": [(b"content-length", b"6")],
        },
        receive,
        send,
    )

    assert not app_called
    assert not receive_called
    assert messages[0]["status"] == 413


@pytest.mark.asyncio
async def test_image_upload_middleware_does_not_limit_other_routes():
    app_called = False

    async def app(scope, receive, send):
        nonlocal app_called
        app_called = True

    async def receive():
        return {"type": "http.request", "body": b"123456", "more_body": False}

    async def send(message):
        pass

    middleware = ImageUploadSizeLimitMiddleware(app, max_bytes=5)
    await middleware(
        {"type": "http", "method": "POST", "path": "/users/auth", "headers": []},
        receive,
        send,
    )

    assert app_called


@pytest.mark.asyncio
async def test_prebuffer_coalesces_many_fragments_without_retaining_envelopes():
    import gc
    import weakref

    envelopes = []
    count = 2000

    async def receive():
        if len(envelopes) < count:
            event = _WeakEnvelope(
                type="http.request", body=b"", more_body=True
            )
            envelopes.append(weakref.ref(event))
            return event
        event = _WeakEnvelope(type="http.request", body=b"ok", more_body=False)
        envelopes.append(weakref.ref(event))
        return event

    async def app(scope, app_receive, send):
        message = await app_receive()
        gc.collect()
        assert sum(reference() is not None for reference in envelopes) <= 1
        assert message == {"type": "http.request", "body": b"ok", "more_body": False}

    async def send(message):
        pass

    middleware = ImageUploadSizeLimitMiddleware(app, max_bytes=5)
    await middleware(
        {"type": "http", "method": "POST", "path": "/images", "headers": []},
        receive,
        send,
    )


@pytest.mark.asyncio
async def test_prebuffer_preserves_fragmented_body_and_disconnect():
    incoming = iter(
        [
            {"type": "http.request", "body": b"first", "more_body": True},
            {"type": "http.request", "body": b"second", "more_body": True},
            {"type": "http.disconnect"},
        ]
    )
    received = []

    async def receive():
        return next(incoming)

    async def app(scope, app_receive, send):
        received.append(await app_receive())
        received.append(await app_receive())

    async def send(message):
        pass

    middleware = ImageUploadSizeLimitMiddleware(app, max_bytes=20)
    await middleware(
        {"type": "http", "method": "POST", "path": "/images", "headers": []},
        receive,
        send,
    )

    assert received == [
        {"type": "http.request", "body": b"firstsecond", "more_body": True},
        {"type": "http.disconnect"},
    ]
