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


def test_upload_cannot_write_outside_image_directory(
    image_storage, png_bytes, monkeypatch
):
    delay = Mock()
    monkeypatch.setattr(images.resize_image, "delay", delay)
    with BytesIO(png_bytes) as content, pytest.raises(HTTPException) as error:
        images.upload_image(
            UploadFile(file=content, filename="../outside.png")
        )
    assert error.value.status_code == 400
    if (image_storage.parent / "outside.png").exists():
        pytest.fail("The upload wrote outside its storage directory")
    delay.assert_not_called()


def test_upload_does_not_store_or_schedule_invalid_image(image_storage, monkeypatch):
    delay = Mock()
    monkeypatch.setattr(images.resize_image, "delay", delay)
    with BytesIO(b"this is not an image") as content, pytest.raises(
        HTTPException
    ) as error:
        images.upload_image(
            UploadFile(file=content, filename="invalid.png")
        )
    assert error.value.status_code == 400
    if (image_storage / "invalid.png").exists():
        pytest.fail("The upload stored non-image bytes")
    delay.assert_not_called()


def test_upload_rejects_extension_that_does_not_match_image(
    image_storage, png_bytes, monkeypatch
):
    delay = Mock()
    monkeypatch.setattr(images.resize_image, "delay", delay)
    with BytesIO(png_bytes) as content, pytest.raises(HTTPException) as error:
        images.upload_image(UploadFile(file=content, filename="lake.jpg"))

    assert error.value.status_code == 400
    assert list(image_storage.iterdir()) == []
    delay.assert_not_called()


def test_upload_rejects_file_over_10_mib(image_storage, monkeypatch):
    delay = Mock()
    monkeypatch.setattr(images.resize_image, "delay", delay)
    content = BytesIO(b"x" * (10 * 1024 * 1024 + 1))
    with content, pytest.raises(HTTPException) as error:
        images.upload_image(UploadFile(file=content, filename="large.png"))

    assert error.value.status_code == 413
    assert list(image_storage.iterdir()) == []
    delay.assert_not_called()


def test_upload_rejects_image_over_pixel_limit(
    image_storage, png_bytes, monkeypatch
):
    delay = Mock()
    monkeypatch.setattr(images.resize_image, "delay", delay)
    monkeypatch.setattr(images, "MAX_IMAGE_PIXELS", 1, raising=False)
    with BytesIO(png_bytes) as content, pytest.raises(HTTPException) as error:
        images.upload_image(UploadFile(file=content, filename="large.png"))

    assert error.value.status_code == 413
    assert list(image_storage.iterdir()) == []
    delay.assert_not_called()


@pytest.mark.parametrize("filename", ["CON.jpg", "NUL.jpg", "bad:name.jpg"])
def test_upload_rejects_windows_reserved_or_invalid_names(
    image_storage, png_bytes, filename, monkeypatch
):
    delay = Mock()
    monkeypatch.setattr(images.resize_image, "delay", delay)
    with BytesIO(png_bytes) as content, pytest.raises(HTTPException) as error:
        images.upload_image(UploadFile(file=content, filename=filename))

    assert error.value.status_code == 400
    assert list(image_storage.iterdir()) == []
    delay.assert_not_called()


@pytest.mark.parametrize("filename", ["a" * 245 + ".png", "😀" * 125 + ".png"])
def test_upload_rejects_name_too_long_for_thumbnail_suffix(
    image_storage, png_bytes, filename, monkeypatch
):
    delay = Mock()
    monkeypatch.setattr(images.resize_image, "delay", delay)
    with BytesIO(png_bytes) as content, pytest.raises(HTTPException) as error:
        images.upload_image(UploadFile(file=content, filename=filename))

    assert error.value.status_code == 400
    assert list(image_storage.iterdir()) == []
    delay.assert_not_called()


def test_upload_rejects_truncated_image_without_storing_it(
    image_storage, png_bytes, monkeypatch
):
    delay = Mock()
    monkeypatch.setattr(images.resize_image, "delay", delay)
    with BytesIO(png_bytes[:-12]) as content, pytest.raises(HTTPException) as error:
        images.upload_image(UploadFile(file=content, filename="truncated.png"))

    assert error.value.status_code == 400
    assert list(image_storage.iterdir()) == []
    delay.assert_not_called()


def test_upload_returns_503_and_removes_only_its_file_on_known_broker_failure(
    image_storage, png_bytes, monkeypatch
):
    from kombu.exceptions import OperationalError

    existing = image_storage / "keep.png"
    existing.write_bytes(b"existing file")
    delay = Mock(side_effect=OperationalError("broker unavailable"))
    monkeypatch.setattr(images.resize_image, "delay", delay)

    with BytesIO(png_bytes) as content, pytest.raises(HTTPException) as error:
        images.upload_image(UploadFile(file=content, filename="lake.png"))

    assert error.value.status_code == 503
    assert existing.read_bytes() == b"existing file"
    assert not (image_storage / "lake.png").exists()


def test_upload_accepts_ordinary_unicode_filename(image_storage, png_bytes, monkeypatch):
    delay = Mock()
    monkeypatch.setattr(images.resize_image, "delay", delay)
    with BytesIO(png_bytes) as content:
        images.upload_image(
            UploadFile(file=content, filename="озеро_日本.png")
        )

    assert (image_storage / "озеро_日本.png").read_bytes() == png_bytes
    delay.assert_called_once_with("src/static/images/озеро_日本.png")


def test_upload_returns_409_without_overwriting_existing_file(
    image_storage, png_bytes, monkeypatch
):
    existing = image_storage / "lake.png"
    existing.write_bytes(b"original bytes")
    delay = Mock()
    monkeypatch.setattr(images.resize_image, "delay", delay)

    with BytesIO(png_bytes) as content, pytest.raises(HTTPException) as error:
        images.upload_image(UploadFile(file=content, filename="lake.png"))

    assert error.value.status_code == 409
    assert existing.read_bytes() == b"original bytes"
    delay.assert_not_called()
