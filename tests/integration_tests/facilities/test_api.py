import pytest


async def test_get_facilities_matches_database(ac, db):
    response = await ac.get("/facilities/")
    assert response.status_code == 200, response.text
    expected = [facility.model_dump() for facility in await db.facilities.get_all()]
    assert response.json() == expected


async def test_create_facility_persists_data(ac, db):
    response = await ac.post("/facilities/", json={"title": "Wi-Fi"})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert set(data) == {"id", "title"}
    assert isinstance(data["id"], int)
    assert data["title"] == "Wi-Fi"
    stored = await db.facilities.get_one_or_none(id=data["id"])
    assert stored is not None
    assert stored.title == data["title"]
    response = await ac.get("/facilities/")
    assert response.status_code == 200, response.text
    assert data in response.json()


@pytest.mark.parametrize(
    "data", [{}, {"title": None}, {"title": 42}, {"title": ["Wi-Fi"]}]
)
async def test_create_facility_rejects_invalid_body(ac, db, data):
    response = await ac.post("/facilities/", json=data)
    assert response.status_code == 422, response.text
    assert response.json()["detail"]
    assert await db.facilities.get_all() == []
