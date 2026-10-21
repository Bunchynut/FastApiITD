import pytest
from src.Schemas.facilities import FacilityAdd


async def test_get_facilities_matches_database(ac, db):
    response = await ac.get("/facilities/")
    assert response.status_code == 200, response.text
    expected = [facility.model_dump() for facility in await db.facilities.get_all()]
    assert response.json() == expected


async def test_facilities_cache_key_is_stable_and_scoped_to_http_request(ac, db):
    first = await ac.get("/facilities/")
    assert first.status_code == 200, first.text
    assert first.headers.get("X-FastAPI-Cache") == "MISS"
    await db.facilities.add(FacilityAdd(title="Added after cache"))
    await db.commit()

    repeated = await ac.get("/facilities/")
    assert repeated.status_code == 200, repeated.text
    assert repeated.headers.get("X-FastAPI-Cache") == "HIT"
    assert repeated.json() == first.json()


async def test_create_facility_persists_data(admin_ac, ac, db):
    response = await admin_ac.post("/facilities/", json={"title": "Wi-Fi"})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert set(data) == {"id", "title"}
    assert isinstance(data["id"], int)
    assert data["title"] == "Wi-Fi"
    stored = await db.facilities.get_one_or_none(id=data["id"])
    assert stored is not None
    assert stored.title == data["title"]
    response = await admin_ac.get("/facilities/")
    assert response.status_code == 200, response.text
    assert data in response.json()


async def test_create_facility_rejects_title_over_database_width(admin_ac, db):
    response = await admin_ac.post("/facilities/", json={"title": "x" * 101})

    assert response.status_code == 422
    assert any(error["loc"] == ["body", "title"] for error in response.json()["detail"])
    assert await db.facilities.get_all() == []


async def test_create_facility_accepts_title_at_database_width(admin_ac, db):
    title = "x" * 100
    response = await admin_ac.post("/facilities/", json={"title": title})

    assert response.status_code == 200, response.text
    facility_id = response.json()["data"]["id"]
    saved = await db.facilities.get_one_or_none(id=facility_id)
    assert saved is not None
    assert saved.title == title


async def test_create_facility_rejects_nul_title_without_writing(admin_ac, db):
    response = await admin_ac.post("/facilities/", json={"title": "bad\u0000text"})

    assert response.status_code == 422, response.text
    assert await db.facilities.get_all() == []


@pytest.mark.parametrize(
    "data", [{}, {"title": None}, {"title": 42}, {"title": ["Wi-Fi"]}]
)
async def test_create_facility_rejects_invalid_body(admin_ac, db, data):
    response = await admin_ac.post("/facilities/", json=data)
    assert response.status_code == 422, response.text
    assert response.json()["detail"]
    assert await db.facilities.get_all() == []
