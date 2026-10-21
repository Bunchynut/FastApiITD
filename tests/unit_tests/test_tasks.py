from datetime import date
from unittest.mock import AsyncMock, Mock

import pytest
from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories import booking as booking_module
from src.tasks import tasks


@pytest.fixture
def image_storage(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "src" / "static" / "images"
    folder.mkdir(parents=True)
    return folder


def thumbnail_storage(image_storage):
    folder = image_storage / "thumbnails"
    return folder


@pytest.mark.parametrize(
    "filename, image_format", [("lake.png", "PNG"), ("lake.jpg", "JPEG")]
)
def test_resize_produces_readable_sizes_and_preserves_original(
    image_storage, filename, image_format
):
    original = image_storage / filename
    Image.new("RGB", (80, 40), (10, 80, 190)).save(original, format=image_format)
    original_bytes = original.read_bytes()

    tasks.resize_image.run(str(original))

    thumbnails = thumbnail_storage(image_storage)
    for width, height in [(1000, 500), (500, 250), (200, 100)]:
        path = thumbnails / f"lake_{width}px{original.suffix}"
        with Image.open(path) as resized:
            resized.load()
            assert resized.size == (width, height)
            assert resized.format == image_format
            assert all(
                abs(actual - expected) <= 3
                for actual, expected in zip(resized.getpixel((0, 0)), (10, 80, 190))
            )
    assert original.read_bytes() == original_bytes
    assert len(list(thumbnails.iterdir())) == 3


def test_resize_missing_file_creates_no_output(image_storage):
    with pytest.raises(FileNotFoundError):
        tasks.resize_image.run(str(image_storage / "missing.png"))
    assert list(image_storage.iterdir()) == []


def test_resize_corrupt_image_creates_no_output(image_storage):
    original = image_storage / "broken.png"
    original.write_bytes(b"not a png")
    with pytest.raises(UnidentifiedImageError):
        tasks.resize_image.run(str(original))
    assert list(image_storage.iterdir()) == [original]


def test_resize_does_not_overwrite_original_with_output_name(image_storage):
    original = image_storage / "photo.png"
    Image.new("RGB", (80, 40), "blue").save(original)
    collision = image_storage / "photo_200px.png"
    collision.write_bytes(b"keep this original")

    tasks.resize_image.run(str(original))

    assert collision.read_bytes() == b"keep this original"
    assert (thumbnail_storage(image_storage) / "photo_200px.png").is_file()


def test_resize_reuses_valid_thumbnail_byte_for_byte(image_storage):
    original = image_storage / "photo.png"
    Image.new("RGB", (80, 40), "blue").save(original)
    tasks.resize_image.run(str(original))
    thumbnails = thumbnail_storage(image_storage)
    existing = thumbnails / "photo_200px.png"
    existing_bytes = existing.read_bytes()

    tasks.resize_image.run(str(original))

    assert existing.read_bytes() == existing_bytes


def test_resize_repairs_corrupt_and_zero_byte_thumbnails_atomically(image_storage):
    original = image_storage / "photo.png"
    Image.new("RGB", (80, 40), "blue").save(original)
    original_bytes = original.read_bytes()
    thumbnails = thumbnail_storage(image_storage)
    thumbnails.mkdir()
    (thumbnails / "photo_1000px.png").write_bytes(b"partial")
    (thumbnails / "photo_500px.png").write_bytes(b"")

    tasks.resize_image.run(str(original))

    for size in (1000, 500, 200):
        with Image.open(thumbnails / f"photo_{size}px.png") as output:
            output.load()
            assert output.size == (size, size // 2)
    assert original.read_bytes() == original_bytes


def test_resize_repairs_png_thumbnail_with_truncated_tail(image_storage):
    original = image_storage / "photo.png"
    Image.new("RGB", (80, 40), "blue").save(original)
    original_bytes = original.read_bytes()
    thumbnails = thumbnail_storage(image_storage)
    tasks.resize_image.run(str(original))

    damaged = thumbnails / "photo_200px.png"
    damaged.write_bytes(damaged.read_bytes()[:-5])
    tasks.resize_image.run(str(original))

    for size in (1000, 500, 200):
        with Image.open(thumbnails / f"photo_{size}px.png") as output:
            output.verify()
        with Image.open(thumbnails / f"photo_{size}px.png") as output:
            output.load()
    assert original.read_bytes() == original_bytes


def test_resize_retry_after_partial_failure_completes_all_variants(
    image_storage, monkeypatch
):
    original = image_storage / "photo.png"
    Image.new("RGB", (80, 40), "blue").save(original)
    original_bytes = original.read_bytes()
    thumbnails = thumbnail_storage(image_storage)
    real_save = Image.Image.save
    failed = False

    save_count = 0

    def fail_second_save(image, fp, *args, **kwargs):
        nonlocal save_count
        nonlocal failed
        save_count += 1
        if save_count == 2 and not failed:
            failed = True
            raise OSError("simulated disk interruption")
        return real_save(image, fp, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "save", fail_second_save)
    with pytest.raises(OSError, match="simulated disk interruption"):
        tasks.resize_image.run(str(original))
    assert list(thumbnails.glob(".thumb-*")) == []
    monkeypatch.setattr(Image.Image, "save", real_save)

    tasks.resize_image.run(str(original))

    assert len(list(thumbnails.glob("photo_*px.png"))) == 3
    for size in (1000, 500, 200):
        with Image.open(thumbnails / f"photo_{size}px.png") as output:
            output.load()
    assert original.read_bytes() == original_bytes


def test_resize_replaces_stale_thumbnails_for_retried_new_original(image_storage):
    original = image_storage / "photo.png"
    thumbnails = thumbnail_storage(image_storage)

    Image.new("RGB", (80, 40), "red").save(original)
    tasks.resize_image.run(str(original))
    original.write_bytes(b"different source sentinel")
    Image.new("RGB", (80, 40), "green").save(original)
    retried_original_bytes = original.read_bytes()
    tasks.resize_image.run(str(original))

    for size in (1000, 500, 200):
        with Image.open(thumbnails / f"photo_{size}px.png") as output:
            output.load()
            assert output.getpixel((0, 0)) == (0, 128, 0)
    assert original.read_bytes() == retried_original_bytes

    completed_bytes = {
        path.name: path.read_bytes() for path in thumbnails.glob("photo_*px.png")
    }
    tasks.resize_image.run(str(original))
    assert {
        path.name: path.read_bytes() for path in thumbnails.glob("photo_*px.png")
    } == completed_bytes


@pytest.mark.parametrize("size", [(1, 1000), (2000, 1)])
def test_resize_extreme_aspect_ratios_stay_bounded_and_nonzero(
    image_storage, size, monkeypatch
):
    original_resize = Image.Image.resize

    def bounded_resize(image, output_size, *args, **kwargs):
        width, height = output_size
        assert 1 <= width <= 1000
        assert 1 <= height <= 1000
        assert width * height <= 1_000_000
        return original_resize(image, output_size, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "resize", bounded_resize)
    original = image_storage / "extreme.png"
    Image.new("RGB", size, "blue").save(original)

    tasks.resize_image.run(str(original))

    paths = list(thumbnail_storage(image_storage).glob("extreme_*px.png"))
    assert len(paths) == 3
    for path in paths:
        with Image.open(path) as resized:
            assert resized.width >= 1
            assert resized.height >= 1
            assert resized.width <= 1000
            assert resized.height <= 1000
            assert resized.width * resized.height <= 1_000_000


def test_resize_thin_image_keeps_nonzero_height(image_storage):
    original = image_storage / "thin.png"
    Image.new("RGB", (2000, 1), "blue").save(original)
    tasks.resize_image.run(str(original))
    for width in (1000, 500, 200):
        with Image.open(thumbnail_storage(image_storage) / f"thin_{width}px.png") as resized:
            assert resized.size == (width, 1)


def test_checkin_task_queries_today_bookings_and_closes_session(monkeypatch, capsys):
    class FrozenDate(date):
        @classmethod
        def today(cls):
            return date(2030, 1, 2)

    session = AsyncMock(spec=AsyncSession)
    result = Mock()
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result
    monkeypatch.setattr(tasks, "async_session_maker_null_pull", lambda: session)
    monkeypatch.setattr(booking_module, "date", FrozenDate)

    tasks.send_email_booking_today_checkin.run()

    statement = session.execute.call_args.args[0]
    assert statement.compile().params == {"date_from_1": date(2030, 1, 2)}
    assert "bookings.date_from" in str(statement.whereclause)
    assert "[]" in capsys.readouterr().out
    session.execute.assert_awaited_once()
    session.close.assert_awaited_once_with()
