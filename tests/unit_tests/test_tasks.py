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

    for width, height in [(1000, 500), (500, 250), (200, 100)]:
        path = image_storage / f"lake_{width}px{original.suffix}"
        with Image.open(path) as resized:
            resized.load()
            assert resized.size == (width, height)
            assert resized.format == image_format
            assert all(
                abs(actual - expected) <= 3
                for actual, expected in zip(resized.getpixel((0, 0)), (10, 80, 190))
            )
    assert original.read_bytes() == original_bytes
    assert len(list(image_storage.iterdir())) == 4


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


@pytest.mark.xfail(
    strict=True,
    raises=ValueError,
    reason="resize_image rounds very small output heights down to zero",
)
def test_resize_thin_image_keeps_nonzero_height(image_storage):
    original = image_storage / "thin.png"
    Image.new("RGB", (2000, 1), "blue").save(original)
    tasks.resize_image.run(str(original))
    for width in (1000, 500, 200):
        with Image.open(image_storage / f"thin_{width}px.png") as resized:
            assert resized.size == (width, 1)


@pytest.mark.xfail(
    strict=True,
    raises=AttributeError,
    reason="Check-in helper calls db.bookings.get_bookings_with_today_checkin; real interface is db.booking.get_booking_today_checkin",
)
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
