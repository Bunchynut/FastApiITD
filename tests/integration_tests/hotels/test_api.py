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


async def test_get_hotels_pagination(ac):
    pages = []
    for page in (1, 2, 3, 4):
        response = await ac.get(
            "/hotels", params={**DATES, "page": page, "per_page": 1}
        )
        assert response.status_code == 200, response.text
        pages.append(response.json())
    assert [len(page) for page in pages] == [1, 1, 1, 0]
    assert all(hotel["id"] in {1, 2, 3} for page in pages for hotel in page)


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


@pytest.mark.xfail(
    strict=True,
    raises=AttributeError,
    reason="Hotel POST passes a dict to BaseRepository.add, which requires model_dump().",
)
async def test_create_hotel_persists_data(ac, db):
    data = {"title": "Integration hotel", "location": "Test city"}
    response = await ac.post("/hotels", json=data)
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
async def test_hotel_write_rejects_invalid_body(ac, method, data):
    url = "/hotels" if method == "post" else "/hotels/1"
    response = await getattr(ac, method)(url, json=data)
    assert response.status_code == 422, response.text
    assert response.json()["detail"]


@pytest.mark.xfail(
    strict=True,
    raises=AttributeError,
    reason="Hotel PUT passes a dict to BaseRepository.put, which requires model_dump().",
)
async def test_replace_hotel_persists_both_fields(ac, db):
    data = {"title": "Replacement hotel", "location": "Replacement city"}
    response = await ac.put("/hotels/1", json=data)
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "OK"}
    db.session.expire_all()
    stored = await db.hotels.get_one_or_none(id=1)
    assert (stored.title, stored.location) == (data["title"], data["location"])


@pytest.mark.xfail(
    strict=True,
    raises=AttributeError,
    reason="Hotel PATCH calls commit() on HotelsRepositories instead of DBManager.",
)
async def test_patch_hotel_preserves_unspecified_fields(ac, db):
    original = await db.hotels.get_one_or_none(id=1)
    location = original.location
    response = await ac.patch("/hotels/1", json={"title": "Patched hotel"})
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "OK"}
    db.session.expire_all()
    stored = await db.hotels.get_one_or_none(id=1)
    assert stored.title == "Patched hotel"
    assert stored.location == location


async def test_patch_hotel_rejects_wrong_type(ac):
    response = await ac.patch("/hotels/1", json={"location": ["City"]})
    assert response.status_code == 422, response.text


async def test_delete_hotel_persists_deletion(ac, db):
    hotel = await db.hotels.add(HotelPost(title="Empty hotel", location="City"))
    hotel_id = hotel.id
    await db.commit()
    response = await ac.delete(f"/hotels/{hotel_id}")
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "OK"}
    assert await db.hotels.get_one_or_none(id=hotel_id) is None


async def test_delete_hotel_rejects_invalid_path(ac):
    response = await ac.delete("/hotels/invalid")
    assert response.status_code == 422, response.text
