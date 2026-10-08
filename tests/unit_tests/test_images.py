from io import BytesIO
from unittest.mock import Mock

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image

from src.api import images


@pytest.fixture
def image_storage(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "src" / "static" / "images"
    folder.mkdir(parents=True)
    return folder


@pytest.fixture
def png_bytes():
    with BytesIO() as content:
        Image.new("RGB", (80, 40), (10, 80, 190)).save(content, format="PNG")
        return content.getvalue()


def test_upload_saves_original_before_scheduling_resize(
    image_storage, png_bytes, monkeypatch
):
    scheduled = []

    def schedule(path):
        assert (image_storage / "lake.png").read_bytes() == png_bytes
        scheduled.append(path)

    delay = Mock(side_effect=schedule)
    monkeypatch.setattr(images.resize_image, "delay", delay)
    with BytesIO(png_bytes) as content:
        images.upload_image(UploadFile(file=content, filename="lake.png"))

    assert (image_storage / "lake.png").read_bytes() == png_bytes
    assert scheduled == ["src/static/images/lake.png"]
    delay.assert_called_once_with("src/static/images/lake.png")


@pytest.mark.xfail(
    strict=True,
    raises=FileNotFoundError,
    reason="upload_image assumes src/static/images already exists",
)
def test_upload_creates_image_directory_on_clean_checkout(
    tmp_path, png_bytes, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    delay = Mock()
    monkeypatch.setattr(images.resize_image, "delay", delay)
    with BytesIO(png_bytes) as content:
        images.upload_image(UploadFile(file=content, filename="lake.png"))
    assert (
        tmp_path / "src" / "static" / "images" / "lake.png"
    ).read_bytes() == png_bytes
    delay.assert_called_once_with("src/static/images/lake.png")


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="upload_image uses the supplied filename without preventing path traversal",
)
def test_upload_cannot_write_outside_image_directory(
    image_storage, png_bytes, monkeypatch
):
    delay = Mock()
    monkeypatch.setattr(images.resize_image, "delay", delay)
    with BytesIO(png_bytes) as content:
        try:
            images.upload_image(UploadFile(file=content, filename="../outside.png"))
        except HTTPException as error:
            assert error.status_code in (400, 422)
    assert not (image_storage.parent / "outside.png").exists()
    delay.assert_not_called()


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="upload_image stores non-image content and queues a resize task",
)
def test_upload_does_not_store_or_schedule_invalid_image(image_storage, monkeypatch):
    delay = Mock()
    monkeypatch.setattr(images.resize_image, "delay", delay)
    with BytesIO(b"this is not an image") as content:
        try:
            images.upload_image(UploadFile(file=content, filename="invalid.png"))
        except HTTPException as error:
            assert error.status_code in (400, 422)
    assert not (image_storage / "invalid.png").exists()
    delay.assert_not_called()
