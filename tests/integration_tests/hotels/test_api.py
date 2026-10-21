import pytest

from src.Schemas.Schemas import HotelPost
from src.Schemas.rooms import RoomsPatchSchema

DATES = {"date_from": "2030-08-01", "date_to": "2030-08-10"}


async def test_get_hotels_returns_seeded_data(ac, db):
    response = await ac.get("/hotels", params=DATES)
    assert response.status_code == 200, response.text
    expected = await db.hotels.get_all()
    assert {row["id"] for row in response.json()} == {hotel.id for hotel in expected}
    assert all(set(row) == {"id", "title", "location"} for row in response.json())


@pytest.mark.parametrize(
    ("filters", "expected_ids"),
    [
        ({"id": 2}, {2}),
        ({"title": "SKALA"}, {2}),
        ({"location": "республика алтай"}, {1, 2}),
        ({"title": "resort", "location": "сириус"}, {3}),
        ({"title": "no such hotel"}, set()),
        ({"id": 999999}, set()),
    ],
)
async def test_get_hotels_filters(ac, filters, expected_ids):
    response = await ac.get("/hotels", params={**DATES, **filters})
    assert response.status_code == 200, response.text
    assert {row["id"] for row in response.json()} == expected_ids


async def test_hotel_cache_key_is_stable_and_scoped_to_http_request(ac, db):
    params = {**DATES, "id": 1}
    first = await ac.get("/hotels", params=params)
    assert first.status_code == 200, first.text
    assert first.headers.get("X-FastAPI-Cache") == "MISS"
    await db.hotels.put(id=1, data=HotelPost(title="Changed after cache", location="City"))
    await db.commit()

    repeated = await ac.get("/hotels", params=params)
    assert repeated.status_code == 200, repeated.text
    assert repeated.headers.get("X-FastAPI-Cache") == "HIT"
    assert repeated.json() == first.json()


async def test_hotel_cache_separates_dates_filters_and_pages(ac):
    requests = [
        {**DATES},
        {"date_from": "2031-08-01", "date_to": "2031-08-10"},
        {**DATES, "title": "SKALA"},
        {**DATES, "page": 2, "per_page": 1},
    ]
    for params in requests:
        response = await ac.get("/hotels", params=params)
        assert response.status_code == 200, response.text
        assert response.headers.get("X-FastAPI-Cache") == "MISS"


async def test_hotel_cache_preserves_duplicate_query_parameter_order(ac):
    first = await ac.get(
        "/hotels", params=[("date_from", DATES["date_from"]), ("date_to", DATES["date_to"]), ("id", "1"), ("id", "2")]
    )
    reversed_values = await ac.get(
        "/hotels", params=[("date_from", DATES["date_from"]), ("date_to", DATES["date_to"]), ("id", "2"), ("id", "1")]
    )

    assert first.status_code == reversed_values.status_code == 200
    assert {item["id"] for item in first.json()} != {item["id"] for item in reversed_values.json()}


@pytest.mark.parametrize("field", ["title", "location"])
@pytest.mark.parametrize("method", ["post", "put", "patch"])
async def test_hotel_writes_reject_nul_in_text_fields(admin_ac, db, method, field):
    data = {"title": "Hotel", "location": "City", field: "bad\u0000text"}
    response = await getattr(admin_ac, method)("/hotels" if method == "post" else "/hotels/1", json=data)

    assert response.status_code == 422, response.text
    if method == "post":
        assert await db.hotels.get_one_or_none(title="Hotel") is None


@pytest.mark.parametrize("bad_id", [0, 2147483648])
async def test_hotel_id_filters_reject_ids_outside_postgres_range(ac, bad_id):
    response = await ac.get("/hotels", params={**DATES, "id": bad_id})
    assert response.status_code == 422, response.text


async def test_hotel_id_filter_accepts_postgres_integer_max(ac):
    response = await ac.get("/hotels", params={**DATES, "id": 2147483647})
    assert response.status_code == 200, response.text
    assert response.json() == []


@pytest.mark.parametrize("field", ["title", "location"])
async def test_hotel_text_filters_reject_nul(ac, field):
    response = await ac.get("/hotels", params={**DATES, field: "bad\u0000text"})
    assert response.status_code == 422, response.text


async def test_hotel_path_rejects_ids_outside_postgres_range(admin_ac):
    for bad_id in (0, 2147483648):
        response = await admin_ac.delete(f"/hotels/{bad_id}")
        assert response.status_code == 422, response.text


async def test_hotel_path_accepts_postgres_integer_max(admin_ac):
    response = await admin_ac.delete("/hotels/2147483647")
    assert response.status_code == 404, response.text


@pytest.mark.parametrize("method,path", [("put", "/hotels/0"), ("patch", "/hotels/2147483648")])
async def test_hotel_write_paths_reject_ids_outside_postgres_range(admin_ac, method, path):
    response = await getattr(admin_ac, method)(path, json={"title": "Hotel", "location": "City"})
    assert response.status_code == 422, response.text


async def test_get_hotels_pagination(ac):
    pages = []
    for page in (1, 2, 3, 4):
        response = await ac.get(
            "/hotels", params={**DATES, "page": page, "per_page": 1}
        )
        assert response.status_code == 200, response.text
        pages.append(response.json())
    assert [len(page) for page in pages] == [1, 1, 1, 0]
    assert [hotel["id"] for page in pages for hotel in page] == [1, 2, 3]


@pytest.mark.parametrize(
    ("date_from", "date_to"),
    [("2030-08-10", "2030-08-10"), ("2030-08-11", "2030-08-10")],
)
async def test_get_hotels_rejects_empty_or_reversed_date_interval(ac, date_from, date_to):
    response = await ac.get(
        "/hotels", params={"date_from": date_from, "date_to": date_to}
    )
    assert response.status_code == 422, response.text


async def test_get_hotels_excludes_hotels_without_available_rooms(ac, db):
    await db.rooms.put(RoomsPatchSchema(quantity=0), exclude_unset=True, id=3)
    await db.commit()
    response = await ac.get("/hotels", params=DATES)
    assert response.status_code == 200, response.text
    assert {hotel["id"] for hotel in response.json()} == {1, 3}


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"date_from": DATES["date_from"]},
        {"date_to": DATES["date_to"]},
        {**DATES, "date_from": "invalid"},
        {**DATES, "id": "invalid"},
        {**DATES, "page": 0},
        {**DATES, "page": "invalid"},
        {**DATES, "per_page": 0},
        {**DATES, "per_page": 31},
    ],
)
async def test_get_hotels_rejects_invalid_query(ac, params):
    response = await ac.get("/hotels", params=params)
    assert response.status_code == 422, response.text
    assert response.json()["detail"]


async def test_create_hotel_persists_data(admin_ac, db):
    data = {"title": "Integration hotel", "location": "Test city"}
    response = await admin_ac.post("/hotels", json=data)
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "OK", "data": data}
    stored = await db.hotels.get_one_or_none(title=data["title"])
    assert stored is not None
    assert stored.location == data["location"]


@pytest.mark.parametrize("method", ["post", "put"])
@pytest.mark.parametrize(
    "data",
    [
        {},
        {"title": "Only title"},
        {"location": "Only location"},
        {"title": 3, "location": "City"},
    ],
)
async def test_hotel_write_rejects_invalid_body(admin_ac, method, data):
    url = "/hotels" if method == "post" else "/hotels/1"
    response = await getattr(admin_ac, method)(url, json=data)
    assert response.status_code == 422, response.text
    assert response.json()["detail"]


@pytest.mark.parametrize("method", ["post", "put", "patch"])
@pytest.mark.parametrize("field", ["title", "location"])
async def test_hotel_write_rejects_values_over_database_width(admin_ac, method, field):
    data = {"title": "Hotel", "location": "City", field: "x" * 101}
    url = "/hotels" if method == "post" else "/hotels/1"
    response = await getattr(admin_ac, method)(url, json=data)
    assert response.status_code == 422, response.text


async def test_replace_hotel_persists_both_fields(admin_ac, db):
    data = {"title": "Replacement hotel", "location": "Replacement city"}
    response = await admin_ac.put("/hotels/1", json=data)
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "OK"}
    db.session.expire_all()
    stored = await db.hotels.get_one_or_none(id=1)
    assert (stored.title, stored.location) == (data["title"], data["location"])


async def test_patch_hotel_preserves_unspecified_fields(admin_ac, db):
    original = await db.hotels.get_one_or_none(id=1)
    location = original.location
    response = await admin_ac.patch("/hotels/1", json={"title": "Patched hotel"})
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "OK"}
    db.session.expire_all()
    stored = await db.hotels.get_one_or_none(id=1)
    assert stored.title == "Patched hotel"
    assert stored.location == location


async def test_patch_hotel_rejects_wrong_type(admin_ac):
    response = await admin_ac.patch("/hotels/1", json={"location": ["City"]})
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("field", ["title", "location"])
async def test_patch_hotel_rejects_null_non_nullable_fields(admin_ac, field):
    response = await admin_ac.patch("/hotels/1", json={field: None})
    assert response.status_code == 422, response.text


async def test_empty_hotel_patch_is_safe_noop(admin_ac, db):
    original = await db.hotels.get_one_or_none(id=1)
    response = await admin_ac.patch("/hotels/1", json={})
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "OK"}
    db.session.expire_all()
    stored = await db.hotels.get_one_or_none(id=1)
    assert (stored.title, stored.location) == (original.title, original.location)


async def test_delete_hotel_persists_deletion(admin_ac, db):
    hotel = await db.hotels.add(HotelPost(title="Empty hotel", location="City"))
    hotel_id = hotel.id
    await db.commit()
    response = await admin_ac.delete(f"/hotels/{hotel_id}")
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "OK"}
    assert await db.hotels.get_one_or_none(id=hotel_id) is None


async def test_delete_hotel_rejects_invalid_path(admin_ac):
    response = await admin_ac.delete("/hotels/invalid")
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
async def test_hotel_write_returns_404_for_missing_target(admin_ac, method):
    payload = {"title": "Absent", "location": "Nowhere"}
    response = await admin_ac.request(method, "/hotels/999999", json=payload)
    assert response.status_code == 404, response.text


async def test_delete_hotel_with_rooms_returns_conflict(admin_ac, db):
    response = await admin_ac.delete("/hotels/1")
    assert response.status_code == 409, response.text
    assert await db.hotels.get_one_or_none(id=1) is not None
    assert await db.rooms.get_one_or_none(id=1) is not None
