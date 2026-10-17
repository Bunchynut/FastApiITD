from datetime import date

import pytest
from sqlalchemy import func, select

from src.Schemas.booking import BookingAdd
from src.Schemas.rooms import RoomsPatchSchema
from src.model.bookings import BookingORM


class InvalidStayAccepted(Exception):
    pass


class SoldOutNotHandled(Exception):
    pass


class MissingBookingList(Exception):
    pass


@pytest.fixture
def booking_data():
    return {"room_id": 1, "date_from": "2027-08-10", "date_to": "2027-08-15"}


async def count_bookings(db):
    return await db.session.scalar(select(func.count()).select_from(BookingORM))


async def test_add_booking(db, auth_ac, booking_data):
    room = await db.rooms.get_one_or_none(id=booking_data["room_id"])
    user = (await db.users.get_all())[0]
    response = await auth_ac.post("/booking", json=booking_data)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "OK"
    assert result["data"]["room_id"] == room.id
    assert result["data"]["user_id"] == user.id
    assert result["data"]["price"] == room.price
    assert result["data"]["date_from"] == booking_data["date_from"]
    assert result["data"]["date_to"] == booking_data["date_to"]
    saved = await db.booking.get_one_or_none(id=result["data"]["id"])
    assert saved is not None
    assert saved.date_from == date(2027, 8, 10)
    assert saved.final_cost == room.price * 5


async def test_booking_uses_server_price_and_authenticated_user(
    db, auth_ac, booking_data
):
    user = (await db.users.get_all())[0]
    response = await auth_ac.post(
        "/booking", json={**booking_data, "price": 1, "user_id": user.id + 1000}
    )
    assert response.status_code == 200, response.text
    saved = await db.booking.get_one_or_none(id=response.json()["data"]["id"])
    assert saved.user_id == user.id
    assert saved.price == (await db.rooms.get_one_or_none(id=1)).price


@pytest.mark.parametrize("method,path", [("post", "/booking"), ("get", "/booking/me")])
async def test_booking_requires_authentication(ac, db, booking_data, method, path):
    kwargs = {"json": booking_data} if method == "post" else {}
    response = await ac.request(method, path, **kwargs)
    assert response.status_code == 401
    assert await count_bookings(db) == 0


async def test_booking_unknown_room_returns_404(auth_ac, db, booking_data):
    response = await auth_ac.post("/booking", json={**booking_data, "room_id": 999999})
    assert response.status_code == 404
    assert await count_bookings(db) == 0


@pytest.mark.parametrize("field", ["room_id", "date_from", "date_to"])
async def test_booking_missing_fields(auth_ac, db, booking_data, field):
    del booking_data[field]
    response = await auth_ac.post("/booking", json=booking_data)
    assert response.status_code == 422
    assert await count_bookings(db) == 0


@pytest.mark.parametrize(
    "field,value",
    [("room_id", "invalid"), ("date_from", "invalid"), ("date_to", "2027-02-30")],
)
async def test_booking_invalid_types(auth_ac, db, booking_data, field, value):
    response = await auth_ac.post("/booking", json={**booking_data, field: value})
    assert response.status_code == 422
    assert await count_bookings(db) == 0


@pytest.mark.xfail(
    strict=True,
    raises=InvalidStayAccepted,
    reason="AddBookingRequest does not reject empty/reversed stay intervals",
)
@pytest.mark.parametrize("date_to", ["2027-08-10", "2027-08-09"])
async def test_booking_rejects_invalid_date_order(auth_ac, db, booking_data, date_to):
    response = await auth_ac.post("/booking", json={**booking_data, "date_to": date_to})
    if response.status_code == 200:
        saved = await db.booking.get_one_or_none(id=response.json()["data"]["id"])
        assert saved.date_from == date.fromisoformat(booking_data["date_from"])
        assert saved.date_to == date.fromisoformat(date_to)
        assert await count_bookings(db) == 1
        raise InvalidStayAccepted("The invalid interval was persisted")
    assert response.status_code == 422
    assert await count_bookings(db) == 0


@pytest.mark.xfail(
    strict=True,
    raises=SoldOutNotHandled,
    reason="BookingRepository.add_booking raises bare Exception on sold-out room instead of HTTP 409",
)
async def test_sold_out_booking_returns_conflict(auth_ac, db, booking_data):
    await db.rooms.put(RoomsPatchSchema(quantity=1), exclude_unset=True, id=1)
    await db.commit()
    first = await auth_ac.post("/booking", json=booking_data)
    assert first.status_code == 200
    try:
        second = await auth_ac.post("/booking", json=booking_data)
    except Exception as error:
        assert type(error) is Exception
        assert error.args == ()
        assert await count_bookings(db) == 1
        raise SoldOutNotHandled(
            "The second booking was rejected without an HTTP response"
        ) from error
    assert await count_bookings(db) == 1
    assert second.status_code == 409


@pytest.mark.xfail(
    strict=True,
    raises=MissingBookingList,
    reason="BaseRepository.get_filtered returns None, so /booking/me returns null",
)
async def test_my_bookings_empty_list(auth_ac):
    response = await auth_ac.get("/booking/me")
    assert response.status_code == 200
    if response.json() is None:
        raise MissingBookingList("Expected an empty list, got null")
    assert response.json() == []


@pytest.mark.xfail(
    strict=True,
    raises=MissingBookingList,
    reason="BaseRepository.get_filtered discards mapped rows, so /booking/me cannot return owned bookings",
)
async def test_my_bookings_contains_only_current_user(
    auth_ac, db, user_data, booking_data
):
    own = await auth_ac.post("/booking", json=booking_data)
    assert own.status_code == 200
    other_data = {**user_data, "email": "other@example.com"}
    other_registration = await auth_ac.post("/users/auth", json=other_data)
    assert other_registration.status_code == 200
    other = await db.users.get_user_with_hashed(email=other_data["email"])
    await db.booking.add(
        BookingAdd(
            room_id=1,
            user_id=other.id,
            price=24500,
            date_from=date(2027, 9, 1),
            date_to=date(2027, 9, 2),
        )
    )
    await db.commit()
    response = await auth_ac.get("/booking/me")
    assert response.status_code == 200
    assert await count_bookings(db) == 2
    if response.json() is None:
        raise MissingBookingList("Two bookings exist, but the endpoint returns null")
    assert isinstance(response.json(), list)
    assert [item["id"] for item in response.json()] == [own.json()["data"]["id"]]


@pytest.mark.xfail(
    strict=True,
    raises=AttributeError,
    reason="BookingRepository declares schema instead of mapper; nonempty /booking cannot serialize bookings",
)
async def test_get_all_bookings(admin_ac, booking_data):
    created = await admin_ac.post("/booking", json=booking_data)
    assert created.status_code == 200
    response = await admin_ac.get("/booking")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["status"]] == [
        created.json()["data"]["id"]
    ]


async def test_get_all_bookings_empty(admin_ac):
    response = await admin_ac.get("/booking")
    assert response.status_code == 200
    assert response.json() == {"status": []}
