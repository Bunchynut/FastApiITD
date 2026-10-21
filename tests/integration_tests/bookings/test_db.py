from datetime import date

import pytest
from sqlalchemy import select

from src.Schemas.booking import BookingAdd
from src.model.bookings import BookingORM
from src.repositories import booking as booking_module


@pytest.fixture
async def stored_booking(db, register_user):
    user = (await db.users.get_all())[0]
    data = BookingAdd(
        date_from=date(2027, 8, 10),
        date_to=date(2027, 8, 15),
        price=2999,
        user_id=user.id,
        room_id=1,
    )
    return await db.booking.add(data)


async def test_booking_crud(db, stored_booking):
    found = await db.booking.get_one_or_none(id=stored_booking.id)
    assert found.room_id == 1
    assert found.final_cost == 2999 * 5
    updated = BookingAdd(
        date_from=date(2027, 8, 10),
        date_to=date(2027, 8, 20),
        price=4000,
        user_id=found.user_id,
        room_id=1,
    )
    await db.booking.put(updated, id=found.id)
    await db.session.refresh(found)
    assert found.date_to == date(2027, 8, 20)
    assert found.price == 4000
    assert found.final_cost == 40000
    await db.booking.delete(id=found.id)
    assert await db.booking.get_one_or_none(id=found.id) is None
    await db.commit()


async def test_unknown_booking_returns_none(db):
    assert await db.booking.get_one_or_none(id=999999) is None


async def test_booking_get_all_maps_rows(db, stored_booking):
    rows = await db.booking.get_all()
    assert [row.id for row in rows] == [stored_booking.id]
    assert rows[0].model_dump()["price"] == 2999


async def test_booking_get_filtered_returns_matching_rows(db, stored_booking):
    rows = await db.booking.get_filtered(user_id=stored_booking.user_id)
    assert isinstance(rows, list)
    assert [row.id for row in rows] == [stored_booking.id]


async def test_delete_missing_booking_preserves_existing(db, stored_booking):
    await db.booking.delete(id=999999)
    assert await db.booking.get_one_or_none(id=stored_booking.id) is not None


async def test_today_checkins_exclude_other_dates(db, stored_booking, monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2027, 8, 10)

    monkeypatch.setattr(booking_module, "date", FixedDate)
    await db.booking.add(
        BookingAdd(
            date_from=date(2027, 8, 11),
            date_to=date(2027, 8, 12),
            price=100,
            user_id=stored_booking.user_id,
            room_id=1,
        )
    )
    rows = await db.booking.get_booking_today_checkin()
    assert [row.id for row in rows] == [stored_booking.id]


async def test_today_checkins_empty(db, monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2027, 8, 10)

    monkeypatch.setattr(booking_module, "date", FixedDate)
    assert await db.booking.get_booking_today_checkin() == []


async def test_booking_commit_visible_to_another_session(
    db, stored_booking, test_session_factory
):
    await db.commit()
    async with test_session_factory() as session:
        row = await session.scalar(
            select(BookingORM).where(BookingORM.id == stored_booking.id)
        )
        assert row is not None
        assert row.price == 2999
