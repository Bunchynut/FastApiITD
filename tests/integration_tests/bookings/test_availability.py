from datetime import date

import pytest

from src.Schemas.booking import BookingAdd
from src.Schemas.rooms import RoomsPatchSchema
from src.repositories.utils import available_room_ids_for_dates


@pytest.fixture
async def single_room(db, register_user):
    await db.rooms.put(RoomsPatchSchema(quantity=1), exclude_unset=True, id=1)
    user = (await db.users.get_all())[0]
    await db.booking.add(
        BookingAdd(
            room_id=1,
            user_id=user.id,
            date_from=date(2027, 8, 10),
            date_to=date(2027, 8, 15),
            price=24500,
        )
    )
    return user


@pytest.mark.parametrize(
    "start,end,available",
    [
        ("2027-08-01", "2027-08-09", True),
        ("2027-08-16", "2027-08-20", True),
        ("2027-08-10", "2027-08-15", False),
        ("2027-08-11", "2027-08-14", False),
        ("2027-08-09", "2027-08-16", False),
        ("2027-08-09", "2027-08-12", False),
        ("2027-08-12", "2027-08-16", False),
    ],
)
async def test_room_availability_overlap_matrix(db, single_room, start, end, available):
    result = await db.session.execute(
        available_room_ids_for_dates(
            date.fromisoformat(start), date.fromisoformat(end), hotel_id=1
        )
    )
    ids = result.scalars().all()
    assert (1 in ids) is available
    assert 2 in ids
    assert not ({3, 4} & set(ids))


@pytest.mark.parametrize(
    "start,end", [("2027-08-01", "2027-08-10"), ("2027-08-15", "2027-08-20")]
)
async def test_adjacent_stays_do_not_overlap(db, single_room, start, end):
    result = await db.session.execute(
        available_room_ids_for_dates(
            date.fromisoformat(start), date.fromisoformat(end), hotel_id=1
        )
    )
    assert 1 in result.scalars().all()


async def test_availability_without_hotel_filter(db):
    result = await db.session.execute(
        available_room_ids_for_dates(date(2027, 8, 10), date(2027, 8, 15))
    )
    assert set(result.scalars().all()) == {1, 2, 3, 4}


async def test_availability_unknown_hotel_empty(db):
    result = await db.session.execute(
        available_room_ids_for_dates(
            date(2027, 8, 10), date(2027, 8, 15), hotel_id=999999
        )
    )
    assert result.scalars().all() == []


async def test_available_room_can_be_booked_up_to_quantity(db, register_user):
    user = (await db.users.get_all())[0]
    await db.rooms.put(RoomsPatchSchema(quantity=2), exclude_unset=True, id=1)
    data = BookingAdd(
        room_id=1,
        user_id=user.id,
        price=24500,
        date_from=date(2027, 8, 10),
        date_to=date(2027, 8, 15),
    )
    first = await db.booking.add_booking(data, hotel_id=1)
    second = await db.booking.add_booking(data, hotel_id=1)
    assert first.id != second.id
    result = await db.session.execute(
        available_room_ids_for_dates(data.date_from, data.date_to, hotel_id=1)
    )
    assert 1 not in result.scalars().all()


async def test_room_list_and_hotel_search_exclude_sold_out_rooms(ac, db, single_room):
    rooms = await ac.get(
        "/rooms/1/rooms", params={"date_from": "2027-08-11", "date_to": "2027-08-14"}
    )
    assert rooms.status_code == 200
    assert [room["id"] for room in rooms.json()] == [2]
    await db.rooms.put(RoomsPatchSchema(quantity=0), exclude_unset=True, id=2)
    hotels = await ac.get(
        "/hotels", params={"date_from": "2027-08-11", "date_to": "2027-08-14"}
    )
    assert hotels.status_code == 200
    assert {hotel["id"] for hotel in hotels.json()} == {2, 3}


async def test_availability_keeps_capacity_between_disjoint_stays(db, register_user):
    user = (await db.users.get_all())[0]
    await db.rooms.put(RoomsPatchSchema(quantity=2), exclude_unset=True, id=1)
    for start, end in [(1, 4), (6, 9)]:
        await db.booking.add(
            BookingAdd(
                room_id=1,
                user_id=user.id,
                price=24500,
                date_from=date(2027, 8, start),
                date_to=date(2027, 8, end),
            )
        )

    result = await db.session.execute(
        available_room_ids_for_dates(date(2027, 8, 2), date(2027, 8, 8), hotel_id=1)
    )
    room_ids = set(result.scalars().all())
    assert room_ids - {1} == {2}
    assert 1 in room_ids


@pytest.mark.parametrize(
    "stays",
    [
        [(10, 15), (10, 15)],
        [(9, 15), (10, 14)],
    ],
)
async def test_repeated_occupancy_start_counts_each_booking_once(db, register_user, stays):
    user = (await db.users.get_all())[0]
    await db.rooms.put(RoomsPatchSchema(quantity=3), exclude_unset=True, id=1)
    for start, end in stays:
        await db.booking.add(
            BookingAdd(
                room_id=1,
                user_id=user.id,
                price=24500,
                date_from=date(2027, 8, start),
                date_to=date(2027, 8, end),
            )
        )

    requested_start, requested_end = date(2027, 8, 10), date(2027, 8, 12)
    result = await db.session.execute(
        available_room_ids_for_dates(requested_start, requested_end, hotel_id=1)
    )
    assert 1 in result.scalars().all()
    third = await db.booking.add_booking(
        BookingAdd(
            room_id=1,
            user_id=user.id,
            price=24500,
            date_from=requested_start,
            date_to=requested_end,
        ),
        hotel_id=1,
    )
    assert third.id is not None
