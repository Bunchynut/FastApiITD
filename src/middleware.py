class ImageUploadSizeLimitMiddleware:
    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"] != "/images"
        ):
            await self.app(scope, receive, send)
            return

        content_length = next(
            (
                value
                for name, value in scope.get("headers", [])
                if name.lower() == b"content-length"
            ),
            None,
        )
        if content_length is not None:
            try:
                if int(content_length) > self.max_bytes:
                    await self._reject(send)
                    return
            except ValueError:
                pass

        body = bytearray()
        has_request = False
        body_complete = False
        disconnected = False
        while True:
            message = await receive()
            if message["type"] == "http.request":
                has_request = True
                chunk = message.get("body", b"")
                if len(body) + len(chunk) > self.max_bytes:
                    await self._reject(send)
                    return
                if not message.get("more_body", False):
                    body.extend(chunk)
                    body_complete = True
                    break
                body.extend(chunk)
            elif message["type"] == "http.disconnect":
                disconnected = True
                break

        buffered_body = bytes(body)
        body.clear()
        request_pending = has_request
        disconnect_pending = disconnected

        async def buffered_receive():
            nonlocal request_pending, disconnect_pending
            if request_pending:
                request_pending = False
                return {
                    "type": "http.request",
                    "body": buffered_body,
                    "more_body": not body_complete,
                }
            if disconnect_pending:
                disconnect_pending = False
                return {"type": "http.disconnect"}
            return {"type": "http.disconnect"}

        await self.app(scope, buffered_receive, send)

    @staticmethod
    async def _reject(send):
        body = b'{"detail":"Image upload is too large"}'
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
