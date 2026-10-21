import pytest
from sqlalchemy import func, select

from src.model.facilities import FacilitiesORMRoom

from src.Schemas.facilities import FacilityAdd
from src.Schemas.booking import BookingAdd
from src.Schemas.rooms import RoomsPatchSchema


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


async def test_get_room_by_id_without_hotel_id(ac):
    response = await ac.get("/rooms", params={"id": 1})
    assert response.status_code == 200, response.text
    assert response.json()["id"] == 1


async def test_get_room_requires_id(ac):
    response = await ac.get("/rooms")
    assert response.status_code == 422, response.text


async def test_get_room_requires_id_even_when_hotel_id_is_provided(ac):
    response = await ac.get("/rooms", params={"hotel_id": 1})
    assert response.status_code == 422, response.text


@pytest.mark.parametrize(
    "params",
    [
        {"id": 0},
        {"id": 2147483648},
        {"id": 1, "hotel_id": 0},
        {"id": 1, "hotel_id": 2147483648},
    ],
)
async def test_get_room_rejects_query_ids_outside_postgres_range(ac, params):
    response = await ac.get("/rooms", params=params)
    assert response.status_code == 422, response.text


async def test_get_room_query_accepts_postgres_integer_max(ac):
    response = await ac.get("/rooms", params={"id": 2147483647})
    assert response.status_code == 200, response.text
    assert response.json() is None


@pytest.mark.parametrize("field", ["title", "description"])
@pytest.mark.parametrize("method", ["post", "put", "patch"])
async def test_room_writes_reject_nul_in_text_fields(admin_ac, method, field):
    data = {**ROOM_DATA, field: "bad\u0000text"}
    if method == "put":
        data = {**REPLACEMENT, field: "bad\u0000text"}
    elif method == "patch":
        data = {field: "bad\u0000text"}
    response = await getattr(admin_ac, method)("/rooms" if method == "post" else "/rooms/1/1", json=data)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("bad_id", [0, 2147483648])
async def test_room_body_hotel_id_rejects_values_outside_postgres_range(admin_ac, db, bad_id):
    response = await admin_ac.post("/rooms", json={**ROOM_DATA, "hotel_id": bad_id})
    assert response.status_code == 422, response.text
    assert await db.rooms.get_one_or_none(title=ROOM_DATA["title"]) is None


async def test_room_body_hotel_id_accepts_postgres_integer_max(admin_ac, db):
    response = await admin_ac.post(
        "/rooms", json={**ROOM_DATA, "hotel_id": 2147483647}
    )
    assert response.status_code == 404, response.text
    assert await db.rooms.get_one_or_none(title=ROOM_DATA["title"]) is None


@pytest.mark.parametrize("path", ["/rooms/0/rooms", "/rooms/2147483648/rooms", "/rooms/1/rooms", "/rooms/2147483647/rooms"])
async def test_room_path_ids_enforce_postgres_range(admin_ac, path):
    response = await admin_ac.get(path, params=DATES)
    if path in ("/rooms/1/rooms", "/rooms/2147483647/rooms"):
        assert response.status_code == 200, response.text
    else:
        assert response.status_code == 422, response.text


@pytest.mark.parametrize(
    "method,path",
    [
        ("delete", "/rooms/0"),
        ("delete", "/rooms/2147483648"),
        ("put", "/rooms/0/1"),
        ("put", "/rooms/2147483648/1"),
        ("put", "/rooms/1/0"),
        ("put", "/rooms/1/2147483648"),
        ("patch", "/rooms/0/1"),
        ("patch", "/rooms/1/2147483648"),
    ],
)
async def test_room_write_paths_reject_ids_outside_postgres_range(admin_ac, method, path):
    data = REPLACEMENT if method == "put" else {"price": 999}
    response = await admin_ac.request(method, path, json=data)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("method,path", [
    ("delete", "/rooms/2147483647"),
    ("put", "/rooms/2147483647/1"),
    ("patch", "/rooms/1/2147483647"),
])
async def test_room_write_paths_accept_postgres_integer_max(admin_ac, method, path):
    data = REPLACEMENT if method == "put" else {"price": 999}
    response = await admin_ac.request(method, path, json=data)
    assert response.status_code == 404, response.text


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


@pytest.mark.parametrize(
    ("date_from", "date_to"),
    [("2030-08-10", "2030-08-10"), ("2030-08-11", "2030-08-10")],
)
async def test_get_available_rooms_rejects_empty_or_reversed_date_interval(
    ac, date_from, date_to
):
    response = await ac.get(
        "/rooms/1/rooms", params={"date_from": date_from, "date_to": date_to}
    )
    assert response.status_code == 422, response.text


async def test_create_room_persists_data_and_facilities(admin_ac, db):
    facility = await db.facilities.add(FacilityAdd(title="Pool"))
    facility_id = facility.id
    await db.commit()
    data = {**ROOM_DATA, "facilities_ids": [facility_id]}
    response = await admin_ac.post("/rooms", json=data)
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "OK", "data": data}
    stored = await db.rooms.get_one_or_none(
        title=data["title"], hotel_id=data["hotel_id"]
    )
    assert stored is not None
    room_id = stored.id
    response = await admin_ac.get(
        "/rooms", params={"id": room_id, "hotel_id": data["hotel_id"]}
    )
    assert response.status_code == 200, response.text
    assert response.json()["price"] == data["price"]
    assert response.json()["quantity"] == data["quantity"]
    assert response.json()["facilities"] == [{"id": facility_id, "title": "Pool"}]


async def test_create_room_deduplicates_facility_ids(admin_ac, db):
    facility = await db.facilities.add(FacilityAdd(title="Duplicate link"))
    await db.commit()
    response = await admin_ac.post(
        "/rooms", json={**ROOM_DATA, "facilities_ids": [facility.id, facility.id]}
    )
    assert response.status_code == 200, response.text
    room = await db.rooms.get_one_or_none(title=ROOM_DATA["title"])
    count = await db.session.scalar(
        select(func.count()).select_from(FacilitiesORMRoom).where(
            FacilitiesORMRoom.room_id == room.id,
            FacilitiesORMRoom.facility_id == facility.id,
        )
    )
    assert count == 1


async def test_create_room_rejects_missing_hotel(admin_ac, db):
    response = await admin_ac.post("/rooms", json={**ROOM_DATA, "hotel_id": 999999})
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
async def test_create_room_rejects_invalid_body(admin_ac, data):
    response = await admin_ac.post("/rooms", json=data)
    assert response.status_code == 422, response.text
    assert response.json()["detail"]


@pytest.mark.parametrize("field", ["title", "price", "quantity"])
async def test_create_room_requires_persisted_fields(admin_ac, field):
    data = {key: value for key, value in ROOM_DATA.items() if key != field}
    response = await admin_ac.post("/rooms", json=data)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("field", ["price", "quantity"])
@pytest.mark.parametrize("method", ["post", "put", "patch"])
async def test_room_writes_reject_negative_price_and_quantity(admin_ac, method, field):
    data = {**ROOM_DATA, field: -1}
    if method == "put":
        data = {**REPLACEMENT, field: -1}
    elif method == "patch":
        data = {field: -1}
    url = "/rooms" if method == "post" else "/rooms/1/1"
    response = await getattr(admin_ac, method)(url, json=data)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("field", ["price", "quantity"])
@pytest.mark.parametrize("method", ["post", "put", "patch"])
async def test_room_writes_reject_values_over_database_integer_maximum(
    admin_ac, method, field
):
    data = {**ROOM_DATA, field: 2147483648}
    if method == "put":
        data = {**REPLACEMENT, field: 2147483648}
    elif method == "patch":
        data = {field: 2147483648}
    url = "/rooms" if method == "post" else "/rooms/1/1"

    response = await getattr(admin_ac, method)(url, json=data)

    assert response.status_code == 422, response.text
    assert any(error["loc"] == ["body", field] for error in response.json()["detail"])


@pytest.mark.parametrize("method", ["post", "put", "patch"])
async def test_room_writes_persist_integer_maximum(admin_ac, ac, db, method):
    data = {**ROOM_DATA, "price": 2147483647, "quantity": 2147483647}
    if method == "put":
        data = {**REPLACEMENT, "price": 2147483647, "quantity": 2147483647}
    elif method == "patch":
        data = {"price": 2147483647, "quantity": 2147483647}
    url = "/rooms" if method == "post" else "/rooms/1/1"

    response = await getattr(admin_ac, method)(url, json=data)

    assert response.status_code == 200, response.text
    if method == "post":
        stored = await db.rooms.get_one_or_none(title=ROOM_DATA["title"])
        assert stored is not None
        room_id = stored.id
    else:
        room_id = 1
    db.session.expire_all()
    response = await ac.get("/rooms", params={"id": room_id, "hotel_id": 1})
    assert response.status_code == 200, response.text
    assert response.json()["price"] == 2147483647
    assert response.json()["quantity"] == 2147483647


@pytest.mark.parametrize("method", ["post", "put", "patch"])
async def test_room_writes_reject_description_over_database_width(admin_ac, method):
    data = {**ROOM_DATA, "description": "x" * 101}
    if method == "put":
        data = {**REPLACEMENT, "description": "x" * 101}
    elif method == "patch":
        data = {"description": "x" * 101}
    url = "/rooms" if method == "post" else "/rooms/1/1"
    response = await getattr(admin_ac, method)(url, json=data)
    assert response.status_code == 422, response.text


async def test_create_room_defaults_omitted_facilities_to_empty_list(admin_ac, db):
    data = {key: value for key, value in ROOM_DATA.items() if key != "facilities_ids"}
    response = await admin_ac.post("/rooms", json=data)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["facilities_ids"] == []
    stored = await db.rooms.get_one_or_none(title=ROOM_DATA["title"])
    assert stored is not None


async def test_create_room_rejects_null_facilities(admin_ac):
    response = await admin_ac.post("/rooms", json={**ROOM_DATA, "facilities_ids": None})
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("method", ["post", "put", "patch"])
@pytest.mark.parametrize("include_valid_id", [False, True])
async def test_room_writes_reject_missing_facility_ids_atomically(
    admin_ac, db, method, include_valid_id
):
    original_facility = await db.facilities.add(FacilityAdd(title="Original facility"))
    replacement_facility = await db.facilities.add(FacilityAdd(title="Replacement facility"))
    original_id = original_facility.id
    requested_ids = [999999]
    if include_valid_id:
        requested_ids.insert(0, replacement_facility.id)
    await db.rooms_facilities.set_rooms_facility(1, [original_id])
    await db.commit()
    original = await db.rooms.get_one_or_none(id=1)
    original_fields = {
        field: getattr(original, field)
        for field in ("title", "description", "price", "quantity")
    }
    data = {**ROOM_DATA, "title": "Invalid facility room", "facilities_ids": requested_ids}
    if method == "put":
        data = {**REPLACEMENT, "facilities_ids": requested_ids}
    elif method == "patch":
        data = {"title": "Should not be written", "facilities_ids": requested_ids}
    url = "/rooms" if method == "post" else "/rooms/1/1"

    response = await getattr(admin_ac, method)(url, json=data)

    assert response.status_code == 404, response.text
    if method == "post":
        assert await db.rooms.get_one_or_none(title="Invalid facility room") is None
    else:
        db.session.expire_all()
        stored = await db.rooms.get_one_or_none(id=1)
        assert {
            field: getattr(stored, field)
            for field in ("title", "description", "price", "quantity")
        } == original_fields
    result = await db.session.execute(
        select(FacilitiesORMRoom.facility_id).filter_by(room_id=1)
    )
    assert result.scalars().all() == [original_id]


@pytest.mark.parametrize("method", ["post", "put", "patch"])
@pytest.mark.parametrize("facility_id", [2147483648, -2147483649])
async def test_room_writes_reject_facility_ids_outside_postgres_integer_range(
    admin_ac, db, method, facility_id
):
    data = {**ROOM_DATA, "facilities_ids": [facility_id]}
    if method == "put":
        data = {**REPLACEMENT, "facilities_ids": [facility_id]}
    elif method == "patch":
        data = {"facilities_ids": [facility_id]}
    url = "/rooms" if method == "post" else "/rooms/1/1"

    response = await getattr(admin_ac, method)(url, json=data)

    assert response.status_code == 404, response.text
    if method == "post":
        assert await db.rooms.get_one_or_none(title=ROOM_DATA["title"]) is None
    else:
        assert await db.rooms.get_one_or_none(id=1) is not None


async def test_replace_room_persists_fields_and_facilities(admin_ac, ac, db):
    facility = await db.facilities.add(FacilityAdd(title="Parking"))
    facility_id = facility.id
    await db.commit()
    data = {**REPLACEMENT, "facilities_ids": [facility_id]}
    response = await admin_ac.put("/rooms/1/1", json=data)
    assert response.status_code == 200, response.text
    db.session.expire_all()
    stored = await db.rooms.get_one_or_none(id=1)
    for field in ("title", "description", "price", "quantity"):
        assert getattr(stored, field) == data[field]
    response = await admin_ac.get("/rooms", params={"id": 1, "hotel_id": 1})
    assert response.status_code == 200, response.text
    assert response.json()["facilities"] == [{"id": facility_id, "title": "Parking"}]


async def test_replace_room_clears_facilities_when_field_is_omitted(admin_ac, db):
    facility = await db.facilities.add(FacilityAdd(title="Old facility"))
    await db.rooms_facilities.set_rooms_facility(1, [facility.id])
    await db.commit()
    data = {key: value for key, value in REPLACEMENT.items() if key != "facilities_ids"}
    response = await admin_ac.put("/rooms/1/1", json=data)
    assert response.status_code == 200, response.text
    result = await db.session.execute(
        select(FacilitiesORMRoom.facility_id).filter_by(room_id=1)
    )
    assert result.scalars().all() == []


async def test_replace_room_allows_null_description(admin_ac, db):
    response = await admin_ac.put(
        "/rooms/1/1", json={**REPLACEMENT, "description": None}
    )
    assert response.status_code == 200, response.text
    db.session.expire_all()
    assert (await db.rooms.get_one_or_none(id=1)).description is None


async def test_replace_room_returns_status_object(admin_ac):
    response = await admin_ac.put("/rooms/1/1", json=REPLACEMENT)
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "OK"}


@pytest.mark.parametrize(
    "data", [{}, {"title": "Only title"}, {**REPLACEMENT, "price": []}]
)
async def test_replace_room_rejects_invalid_body(admin_ac, data):
    response = await admin_ac.put("/rooms/1/1", json=data)
    assert response.status_code == 422, response.text


async def test_patch_room_preserves_unspecified_fields(admin_ac, db):
    original = await db.rooms.get_one_or_none(id=1)
    title, quantity = original.title, original.quantity
    response = await admin_ac.patch("/rooms/1/1", json={"price": 999})
    assert response.status_code == 200, response.text
    db.session.expire_all()
    stored = await db.rooms.get_one_or_none(id=1)
    assert stored.price == 999
    assert (stored.title, stored.quantity) == (title, quantity)


async def test_patch_room_facilities_only_preserves_room_fields(admin_ac, ac, db):
    facility = await db.facilities.add(FacilityAdd(title="Spa"))
    facility_id = facility.id
    await db.commit()
    original = await db.rooms.get_one_or_none(id=1)
    title, price = original.title, original.price
    response = await admin_ac.patch("/rooms/1/1", json={"facilities_ids": [facility_id]})
    assert response.status_code == 200, response.text
    db.session.expire_all()
    response = await admin_ac.get("/rooms", params={"id": 1, "hotel_id": 1})
    assert response.status_code == 200, response.text
    data = response.json()
    assert (data["title"], data["price"]) == (title, price)
    assert data["facilities"] == [{"id": facility_id, "title": "Spa"}]


async def test_patch_room_omitted_facilities_are_untouched(admin_ac, db):
    facility = await db.facilities.add(FacilityAdd(title="Keep me"))
    await db.rooms_facilities.set_rooms_facility(1, [facility.id])
    await db.commit()
    response = await admin_ac.patch("/rooms/1/1", json={"price": 999})
    assert response.status_code == 200, response.text
    result = await db.session.execute(
        select(FacilitiesORMRoom.facility_id).filter_by(room_id=1)
    )
    assert result.scalars().all() == [facility.id]


async def test_patch_room_rejects_null_facilities(admin_ac):
    response = await admin_ac.patch("/rooms/1/1", json={"facilities_ids": None})
    assert response.status_code == 422, response.text


async def test_patch_room_allows_null_description(admin_ac, db):
    response = await admin_ac.patch("/rooms/1/1", json={"description": None})
    assert response.status_code == 200, response.text
    db.session.expire_all()
    assert (await db.rooms.get_one_or_none(id=1)).description is None


async def test_patch_room_returns_status_object(admin_ac):
    response = await admin_ac.patch("/rooms/1/1", json={"facilities_ids": []})
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "OK"}


@pytest.mark.parametrize("data", [{"price": []}, {"facilities_ids": ["invalid"]}])
async def test_patch_room_rejects_wrong_types(admin_ac, data):
    response = await admin_ac.patch("/rooms/1/1", json=data)
    assert response.status_code == 422, response.text


async def test_delete_room_persists_deletion(admin_ac, db):
    response = await admin_ac.delete("/rooms/1")
    assert response.status_code == 200, response.text
    assert await db.rooms.get_one_or_none(id=1) is None


async def test_delete_room_returns_status_object(admin_ac):
    response = await admin_ac.delete("/rooms/1")
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "OK"}


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("delete", "/rooms/invalid"),
        ("put", "/rooms/invalid/1"),
        ("patch", "/rooms/1/invalid"),
    ],
)
async def test_room_writes_reject_invalid_path(admin_ac, method, url):
    response = await admin_ac.request(method, url, json=REPLACEMENT)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
async def test_room_write_returns_404_for_missing_target(admin_ac, method):
    data = REPLACEMENT if method == "put" else ({"price": 999} if method == "patch" else None)
    response = await admin_ac.request(method, "/rooms/999999/1" if method != "delete" else "/rooms/999999", json=data)
    assert response.status_code == 404, response.text


async def test_delete_room_with_booking_returns_conflict(admin_ac, db, user_data):
    user = await db.users.get_user_with_hashed(email=user_data["email"])
    await db.booking.add(
        BookingAdd(
            date_from="2030-08-01",
            date_to="2030-08-05",
            price=100,
            user_id=user.id,
            room_id=1,
        )
    )
    await db.commit()
    response = await admin_ac.delete("/rooms/1")
    assert response.status_code == 409, response.text
    assert await db.rooms.get_one_or_none(id=1) is not None


@pytest.mark.parametrize("method", ["put", "patch"])
async def test_room_write_with_wrong_hotel_preserves_room_and_facilities(
    admin_ac, db, method
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

    response = await admin_ac.request(method, "/rooms/1/2", json=data)

    db.session.expire_all()
    stored = await db.rooms.get_one_or_none(id=1)
    assert {field: getattr(stored, field) for field in fields} == original_values
    result = await db.session.execute(
        select(FacilitiesORMRoom.facility_id).filter_by(room_id=1)
    )
    facility_ids = result.scalars().all()
    assert facility_ids == [original_id]
    assert response.status_code == 404
