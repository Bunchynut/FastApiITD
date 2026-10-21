from io import BytesIO
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from PIL import Image

from src.api import dependencies, images
from src.middleware import ImageUploadSizeLimitMiddleware


def upload_app(max_bytes=1024):
    app = FastAPI()
    app.add_middleware(ImageUploadSizeLimitMiddleware, max_bytes=max_bytes)
    app.include_router(images.router)
    app.dependency_overrides[dependencies.require_admin] = lambda: object()
    return app


def png_bytes():
    with BytesIO() as content:
        Image.new("RGB", (10, 10), "blue").save(content, format="PNG")
        return content.getvalue()


def jpeg_bytes():
    with BytesIO() as content:
        Image.new("RGB", (10, 10), "blue").save(content, format="JPEG")
        return content.getvalue()


@pytest.mark.asyncio
async def test_multipart_route_rejects_truncated_image_before_writing(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    delay = Mock()
    monkeypatch.setattr(images.resize_image, "delay", delay)
    data = png_bytes()[:-5]

    async with AsyncClient(
        transport=ASGITransport(app=upload_app()), base_url="http://test"
    ) as client:
        response = await client.post(
            "/images", files={"file": ("broken.png", data, "image/png")}
        )

    assert response.status_code == 400
    assert not (tmp_path / "src" / "static" / "images" / "broken.png").exists()
    delay.assert_not_called()


@pytest.mark.asyncio
async def test_multipart_route_rejects_truncated_jpeg_before_writing(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    delay = Mock()
    monkeypatch.setattr(images.resize_image, "delay", delay)
    data = jpeg_bytes()[:-2]

    async with AsyncClient(
        transport=ASGITransport(app=upload_app()), base_url="http://test"
    ) as client:
        response = await client.post(
            "/images", files={"file": ("broken.jpg", data, "image/jpeg")}
        )

    assert response.status_code == 400
    assert not (tmp_path / "src" / "static" / "images" / "broken.jpg").exists()
    delay.assert_not_called()


@pytest.mark.asyncio
async def test_chunked_multipart_route_rejects_body_over_limit(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    delay = Mock()
    monkeypatch.setattr(images.resize_image, "delay", delay)
    boundary = "chunked-upload-boundary"
    header = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="large.png"\r\n'
        "Content-Type: image/png\r\n\r\n"
    ).encode()
    ending = f"\r\n--{boundary}--\r\n".encode()

    async def body():
        yield header + b"x" * 2000
        yield ending

    async with AsyncClient(
        transport=ASGITransport(app=upload_app(max_bytes=1024)),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/images",
            content=body(),
            headers={"content-type": f"multipart/form-data; boundary={boundary}"},
        )

    assert response.status_code == 413
    assert not (tmp_path / "src" / "static" / "images" / "large.png").exists()
    delay.assert_not_called()
