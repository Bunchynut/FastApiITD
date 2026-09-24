from datetime import date

from src.Schemas.booking import BookingAdd



async def test_booking_crud(db,register_user):
    user = (await db.users.get_all())[0].id
    room = (await db.rooms.get_all())[0].id
    booking_data = BookingAdd(
        date_from=date(year=2026, month=8, day=10),
        date_to=date(year=2026, month=8, day=15),
        price=2999,
        user_id=user,
        room_id=room,
    )
    new_booking = await db.booking.add(booking_data)

    b = await db.booking.get_one_or_none(id=new_booking.id)
    assert b
    assert b.id == new_booking.id


    update_book_data = BookingAdd(
        date_from=date(year=2026, month=8, day=10),
        date_to=date(year=2026, month=8, day=20),
        price=2999,
        user_id=user,
        room_id=room,
    )
    await db.booking.put(update_book_data, id=new_booking.id)
    update_book = await db.booking.get_one_or_none(id=new_booking.id)
    assert update_book
    assert update_book.id == new_booking.id
    assert update_book.date_to == date(year=2026, month=8, day=20)


    await db.booking.delete(id=new_booking.id)
    b = await db.booking.get_one_or_none(id=new_booking.id)
    assert not b

    await db.commit()