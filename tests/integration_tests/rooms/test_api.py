import pytest
from sqlalchemy import select

from src.model.facilities import FacilitiesORMRoom

from src.Schemas.facilities import FacilityAdd
from src.Schemas.rooms import RoomsPatchSchema


class InvalidRoomStatusShape(Exception):
    pass


class WrongHotelFacilitiesChanged(Exception):
    pass


DATES = {"date_from": "2030-08-01", "date_to": "2030-08-10"}
ROOM_DATA = {
    "hotel_id": 1,
    "title": "Integration room",
    "description": "Room created by an API test",
    "price": 1250,
    "quantity": 2,
    "facilities_ids": [],
}
REPLACEMENT = {
    "title": "Replacement room",
    "description": "Updated description",
    "price": 1500,
    "quantity": 3,
    "facilities_ids": [],
}


async def test_get_room_returns_saved_fields_and_facilities(ac, db):
    facility = await db.facilities.add(FacilityAdd(title="Wi-Fi"))
    facility_id = facility.id
    await db.rooms_facilities.set_rooms_facility(1, [facility_id])
    await db.commit()
    response = await ac.get("/rooms", params={"id": 1, "hotel_id": 1})
    assert response.status_code == 200, response.text
    data = response.json()
    stored = await db.rooms.get_one_or_none(id=1)
    for field in ("id", "hotel_id", "title", "description", "price", "quantity"):
        assert data[field] == getattr(stored, field)
    assert data["facilities"] == [{"id": facility_id, "title": "Wi-Fi"}]


@pytest.mark.parametrize(
    "params", [{"id": 999999, "hotel_id": 1}, {"id": 1, "hotel_id": 2}]
)
async def test_get_room_does_not_match_missing_or_wrong_hotel(ac, params):
    response = await ac.get("/rooms", params=params)
    assert response.status_code == 200, response.text
    assert response.json() is None


@pytest.mark.parametrize(
    "params", [{"id": "invalid", "hotel_id": 1}, {"id": 1, "hotel_id": "invalid"}]
)
async def test_get_room_rejects_wrong_query_types(ac, params):
    response = await ac.get("/rooms", params=params)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize(
    ("hotel_id", "expected_ids"), [(1, {1, 2}), (2, {3}), (3, {4}), (999999, set())]
)
async def test_get_available_rooms_filters_by_hotel(ac, hotel_id, expected_ids):
    response = await ac.get(f"/rooms/{hotel_id}/rooms", params=DATES)
    assert response.status_code == 200, response.text
    assert {room["id"] for room in response.json()} == expected_ids
    assert all(room["hotel_id"] == hotel_id for room in response.json())
    assert all(room["facilities"] == [] for room in response.json())


async def test_get_available_rooms_excludes_zero_quantity(ac, db):
    await db.rooms.put(RoomsPatchSchema(quantity=0), exclude_unset=True, id=1)
    await db.commit()
    response = await ac.get("/rooms/1/rooms", params=DATES)
    assert response.status_code == 200, response.text
    assert {room["id"] for room in response.json()} == {2}


@pytest.mark.parametrize(
    ("hotel_id", "params"),
    [
        (1, {}),
        (1, {"date_from": DATES["date_from"]}),
        (1, {**DATES, "date_to": "invalid"}),
        ("invalid", DATES),
    ],
)
async def test_get_available_rooms_rejects_invalid_query(ac, hotel_id, params):
    response = await ac.get(f"/rooms/{hotel_id}/rooms", params=params)
    assert response.status_code == 422, response.text
    assert response.json()["detail"]


@pytest.mark.xfail(
    strict=True,
    raises=AttributeError,
    reason="Room POST passes a dict to BaseRepository.add, which requires model_dump().",
)
async def test_create_room_persists_data_and_facilities(ac, db):
    facility = await db.facilities.add(FacilityAdd(title="Pool"))
    facility_id = facility.id
    await db.commit()
    data = {**ROOM_DATA, "facilities_ids": [facility_id]}
    response = await ac.post("/rooms", json=data)
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "OK", "data": data}
    stored = await db.rooms.get_one_or_none(
        title=data["title"], hotel_id=data["hotel_id"]
    )
    assert stored is not None
    room_id = stored.id
    response = await ac.get(
        "/rooms", params={"id": room_id, "hotel_id": data["hotel_id"]}
    )
    assert response.status_code == 200, response.text
    assert response.json()["price"] == data["price"]
    assert response.json()["quantity"] == data["quantity"]
    assert response.json()["facilities"] == [{"id": facility_id, "title": "Pool"}]


async def test_create_room_rejects_missing_hotel(ac, db):
    response = await ac.post("/rooms", json={**ROOM_DATA, "hotel_id": 999999})
    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Неверный айди отеля"
    assert await db.rooms.get_one_or_none(title=ROOM_DATA["title"]) is None


@pytest.mark.parametrize(
    "data",
    [
        {},
        {**ROOM_DATA, "hotel_id": "invalid"},
        {**ROOM_DATA, "price": "invalid"},
        {**ROOM_DATA, "quantity": []},
        {**ROOM_DATA, "facilities_ids": ["invalid"]},
    ],
)
async def test_create_room_rejects_invalid_body(ac, data):
    response = await ac.post("/rooms", json=data)
    assert response.status_code == 422, response.text
    assert response.json()["detail"]


async def test_replace_room_persists_fields_and_facilities(ac, db):
    facility = await db.facilities.add(FacilityAdd(title="Parking"))
    facility_id = facility.id
    await db.commit()
    data = {**REPLACEMENT, "facilities_ids": [facility_id]}
    response = await ac.put("/rooms/1/1", json=data)
    assert response.status_code == 200, response.text
    db.session.expire_all()
    stored = await db.rooms.get_one_or_none(id=1)
    for field in ("title", "description", "price", "quantity"):
        assert getattr(stored, field) == data[field]
    response = await ac.get("/rooms", params={"id": 1, "hotel_id": 1})
    assert response.status_code == 200, response.text
    assert response.json()["facilities"] == [{"id": facility_id, "title": "Parking"}]


@pytest.mark.xfail(
    strict=True,
    raises=InvalidRoomStatusShape,
    reason="Room PUT returns a set, serialized as a list, instead of a status object.",
)
async def test_replace_room_returns_status_object(ac):
    response = await ac.put("/rooms/1/1", json=REPLACEMENT)
    assert response.status_code == 200, response.text
    if isinstance(response.json(), list) and set(response.json()) == {"status", "OK"}:
        raise InvalidRoomStatusShape("A Python set was serialized as a JSON list")
    assert response.json() == {"status": "OK"}


@pytest.mark.parametrize(
    "data", [{}, {"title": "Only title"}, {**REPLACEMENT, "price": []}]
)
async def test_replace_room_rejects_invalid_body(ac, data):
    response = await ac.put("/rooms/1/1", json=data)
    assert response.status_code == 422, response.text


@pytest.mark.xfail(
    strict=True,
    raises=TypeError,
    reason="Room PATCH passes data both positionally and by keyword to BaseRepository.put.",
)
async def test_patch_room_preserves_unspecified_fields(ac, db):
    original = await db.rooms.get_one_or_none(id=1)
    title, quantity = original.title, original.quantity
    response = await ac.patch("/rooms/1/1", json={"price": 999})
    assert response.status_code == 200, response.text
    db.session.expire_all()
    stored = await db.rooms.get_one_or_none(id=1)
    assert stored.price == 999
    assert (stored.title, stored.quantity) == (title, quantity)


async def test_patch_room_facilities_only_preserves_room_fields(ac, db):
    facility = await db.facilities.add(FacilityAdd(title="Spa"))
    facility_id = facility.id
    await db.commit()
    original = await db.rooms.get_one_or_none(id=1)
    title, price = original.title, original.price
    response = await ac.patch("/rooms/1/1", json={"facilities_ids": [facility_id]})
    assert response.status_code == 200, response.text
    db.session.expire_all()
    response = await ac.get("/rooms", params={"id": 1, "hotel_id": 1})
    assert response.status_code == 200, response.text
    data = response.json()
    assert (data["title"], data["price"]) == (title, price)
    assert data["facilities"] == [{"id": facility_id, "title": "Spa"}]


@pytest.mark.xfail(
    strict=True,
    raises=InvalidRoomStatusShape,
    reason="Room PATCH returns a set, serialized as a list, instead of a status object.",
)
async def test_patch_room_returns_status_object(ac):
    response = await ac.patch("/rooms/1/1", json={"facilities_ids": []})
    assert response.status_code == 200, response.text
    if isinstance(response.json(), list) and set(response.json()) == {"status", "OK"}:
        raise InvalidRoomStatusShape("A Python set was serialized as a JSON list")
    assert response.json() == {"status": "OK"}


@pytest.mark.parametrize("data", [{"price": []}, {"facilities_ids": ["invalid"]}])
async def test_patch_room_rejects_wrong_types(ac, data):
    response = await ac.patch("/rooms/1/1", json=data)
    assert response.status_code == 422, response.text


async def test_delete_room_persists_deletion(ac, db):
    response = await ac.delete("/rooms/1")
    assert response.status_code == 200, response.text
    assert await db.rooms.get_one_or_none(id=1) is None


@pytest.mark.xfail(
    strict=True,
    raises=InvalidRoomStatusShape,
    reason="Room DELETE returns a set, serialized as a list, instead of a status object.",
)
async def test_delete_room_returns_status_object(ac):
    response = await ac.delete("/rooms/1")
    assert response.status_code == 200, response.text
    if isinstance(response.json(), list) and set(response.json()) == {"status", "OK"}:
        raise InvalidRoomStatusShape("A Python set was serialized as a JSON list")
    assert response.json() == {"status": "OK"}


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("delete", "/rooms/invalid"),
        ("put", "/rooms/invalid/1"),
        ("patch", "/rooms/1/invalid"),
    ],
)
async def test_room_writes_reject_invalid_path(ac, method, url):
    response = await ac.request(method, url, json=REPLACEMENT)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("method", ["put", "patch"])
@pytest.mark.xfail(
    strict=True,
    raises=WrongHotelFacilitiesChanged,
    reason="Room PUT/PATCH filters room fields by hotel_id but updates facilities by room_id alone, changing another hotel's room",
)
async def test_room_write_with_wrong_hotel_preserves_room_and_facilities(
    ac, db, method
):
    original_facility = await db.facilities.add(FacilityAdd(title="Original"))
    new_facility = await db.facilities.add(FacilityAdd(title="Replacement"))
    original_id, new_id = original_facility.id, new_facility.id
    await db.rooms_facilities.set_rooms_facility(1, [original_id])
    await db.commit()
    original = await db.rooms.get_one_or_none(id=1)
    fields = ("title", "description", "price", "quantity", "hotel_id")
    original_values = {field: getattr(original, field) for field in fields}
    data = (
        {**REPLACEMENT, "facilities_ids": [new_id]}
        if method == "put"
        else {"facilities_ids": [new_id]}
    )

    response = await ac.request(method, "/rooms/1/2", json=data)

    db.session.expire_all()
    stored = await db.rooms.get_one_or_none(id=1)
    assert {field: getattr(stored, field) for field in fields} == original_values
    result = await db.session.execute(
        select(FacilitiesORMRoom.facility_id).filter_by(room_id=1)
    )
    facility_ids = result.scalars().all()
    if facility_ids == [new_id]:
        assert response.status_code == 200
        raise WrongHotelFacilitiesChanged(
            "Room fields stayed intact, but facilities were replaced using the wrong hotel"
        )
    assert facility_ids == [original_id]
    assert response.status_code == 404
