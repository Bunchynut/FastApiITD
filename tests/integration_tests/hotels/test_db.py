from datetime import date

import pytest
from sqlalchemy import event

from src.Schemas.Schemas import HotelPatch, HotelPost
from src.Schemas.rooms import RoomsPatchSchema


class MissingFilteredHotels(Exception):
    pass


class MissingPaginationOrder(Exception):
    pass


async def test_hotel_repository_crud(db):
    data = HotelPost(title="Repository hotel", location="New York")
    created = await db.hotels.add(data)
    hotel_id = created.id
    await db.commit()
    stored = await db.hotels.get_one_or_none(id=hotel_id)
    assert stored.title == data.title
    assert stored.location == data.location
    assert hotel_id in {hotel.id for hotel in await db.hotels.get_all()}

    replacement = HotelPost(title="Updated hotel", location="Paris")
    await db.hotels.put(replacement, id=hotel_id)
    await db.commit()
    db.session.expire_all()
    stored = await db.hotels.get_one_or_none(id=hotel_id)
    assert (stored.title, stored.location) == (replacement.title, replacement.location)

    await db.hotels.delete(id=hotel_id)
    await db.commit()
    assert await db.hotels.get_one_or_none(id=hotel_id) is None


async def test_hotel_repository_partial_update(db):
    original = await db.hotels.get_one_or_none(id=1)
    title = original.title
    await db.hotels.put(HotelPatch(location="Updated city"), exclude_unset=True, id=1)
    await db.commit()
    db.session.expire_all()
    stored = await db.hotels.get_one_or_none(id=1)
    assert stored.title == title
    assert stored.location == "Updated city"


async def test_hotel_repository_bulk_insert(db):
    data = [
        HotelPost(title=f"Bulk hotel {index}", location="City") for index in range(2)
    ]
    await db.hotels.add_bulk(data)
    await db.commit()
    stored = await db.hotels.get_all()
    assert {hotel.title for hotel in stored} >= {hotel.title for hotel in data}
    for hotel in data:
        assert (
            await db.hotels.get_one_or_none(title=hotel.title)
        ).location == hotel.location


async def test_hotel_repository_missing_id(db):
    assert await db.hotels.get_one_or_none(id=999999) is None


@pytest.mark.parametrize(
    ("filters", "expected_ids"),
    [
        ({}, {1, 2, 3}),
        ({"title": "SKALA"}, {2}),
        ({"location": "алтай"}, {1, 2}),
        ({"id": 3}, {3}),
        ({"title": "resort", "location": "сириус"}, {3}),
        ({"title": "absent"}, set()),
    ],
)
async def test_hotel_repository_availability_filters(db, filters, expected_ids):
    arguments = {
        "date_from": date(2030, 8, 1),
        "date_to": date(2030, 8, 10),
        "location": None,
        "title": None,
        "id": None,
        "limit": 30,
        "offset": 0,
        **filters,
    }
    hotels = await db.hotels.get_filtered_by_time(**arguments)
    assert {hotel.id for hotel in hotels} == expected_ids


@pytest.mark.xfail(
    strict=True,
    raises=MissingPaginationOrder,
    reason="Hotel pagination uses LIMIT/OFFSET without ORDER BY, allowing duplicate or skipped hotels.",
)
async def test_hotel_repository_pagination_has_stable_order(db):
    statements = []
    connection = db.session.bind.sync_connection

    def capture_sql(conn, cursor, statement, parameters, context, executemany):
        if "SELECT" in statement and "hotels" in statement and "LIMIT" in statement:
            statements.append(statement)

    event.listen(connection, "before_cursor_execute", capture_sql)
    pages = []
    try:
        for offset in range(4):
            hotels = await db.hotels.get_filtered_by_time(
                date_from=date(2030, 8, 1),
                date_to=date(2030, 8, 10),
                location=None,
                title=None,
                id=None,
                limit=1,
                offset=offset,
            )
            pages.append(hotels)
    finally:
        event.remove(connection, "before_cursor_execute", capture_sql)
    assert len(statements) == 4
    if not all("ORDER BY" in statement for statement in statements):
        raise MissingPaginationOrder(
            "The four executed page queries contain no stable ordering"
        )
    assert [len(page) for page in pages] == [1, 1, 1, 0]
    assert {hotel.id for page in pages for hotel in page} == {1, 2, 3}


async def test_hotel_repository_excludes_zero_quantity_rooms(db):
    await db.rooms.put(RoomsPatchSchema(quantity=0), exclude_unset=True, id=3)
    await db.commit()
    hotels = await db.hotels.get_filtered_by_time(
        date_from=date(2030, 8, 1),
        date_to=date(2030, 8, 10),
        location=None,
        title=None,
        id=None,
        limit=30,
        offset=0,
    )
    assert {hotel.id for hotel in hotels} == {1, 3}


@pytest.mark.xfail(
    strict=True,
    raises=MissingFilteredHotels,
    reason="BaseRepository.get_filtered executes its query but never returns the selected models.",
)
async def test_hotel_repository_get_filtered_returns_matching_rows(db):
    hotels = await db.hotels.get_filtered(id=2)
    if hotels is None:
        raise MissingFilteredHotels("Selected rows were discarded")
    assert hotels is not None
    assert [hotel.id for hotel in hotels] == [2]
