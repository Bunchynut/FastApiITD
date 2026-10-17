from io import BytesIO

import pytest
from sqlalchemy import select

from src.model.facilities import FacilitiesORMRoom
from src.model.users import UserRole, UsersOrm

ADMIN_ROUTES = [
    ("post", "/hotels", {"title": "Access test", "location": "City"}),
    ("put", "/hotels/1", {"title": "Replacement", "location": "City"}),
    ("patch", "/hotels/1", {"title": "Replacement"}),
    ("delete", "/hotels/1", None),
    (
        "post",
        "/rooms",
        {
            "hotel_id": 1,
            "title": "Access test room",
            "description": "Access test",
            "price": 100,
            "quantity": 1,
            "facilities_ids": [],
        },
    ),
    (
        "put",
        "/rooms/1/1",
        {
            "title": "Replacement",
            "description": "Access test",
            "price": 100,
            "quantity": 1,
            "facilities_ids": [],
        },
    ),
    ("patch", "/rooms/1/1", {"price": 100}),
    ("delete", "/rooms/1", None),
]
ADDITIONAL_ADMIN_ROUTES = [
    ("post", "/facilities/", {"title": "Access test facility"}),
    ("post", "/images", None),
    ("get", "/booking", None),
]
ADMIN_ROUTES += ADDITIONAL_ADMIN_ROUTES
USER_ROUTES = [
    ("get", "/users/only_auth", None),
    (
        "post",
        "/booking",
        {"room_id": 1, "date_from": "2027-08-10", "date_to": "2027-08-15"},
    ),
    ("get", "/booking/me", None),
]


async def _request(client, method, url, data):
    if url == "/images":
        return await client.post(url, files={"file": ("access.png", b"image")})
    return await client.request(method, url, json=data)


def _block_image_side_effects(monkeypatch):
    from src.api import images

    def unexpected(*args, **kwargs):
        raise AssertionError("unauthorized upload reached a side effect")

    monkeypatch.setattr(images, "open", unexpected, raising=False)
    monkeypatch.setattr(images.shutil, "copyfileobj", unexpected)
    monkeypatch.setattr(images.resize_image, "delay", unexpected)


async def _catalog_state(db):
    facilities = await db.session.execute(
        select(FacilitiesORMRoom.room_id, FacilitiesORMRoom.facility_id).order_by(
            FacilitiesORMRoom.room_id, FacilitiesORMRoom.facility_id
        )
    )
    return (
        await db.hotels.get_all(),
        await db.rooms.get_all(),
        await db.facilities.get_all(),
        facilities.all(),
    )


@pytest.mark.parametrize(("method", "url", "data"), ADMIN_ROUTES)
async def test_write_routes_require_authentication_before_side_effects(
    ac, db, method, url, data, monkeypatch
):
    if url == "/images":
        _block_image_side_effects(monkeypatch)
    state_before = await _catalog_state(db)

    response = await _request(ac, method, url, data)

    assert response.status_code == 401, response.text
    assert await _catalog_state(db) == state_before


@pytest.mark.parametrize(("method", "url", "data"), ADMIN_ROUTES)
async def test_write_routes_reject_regular_users_before_side_effects(
    auth_ac, db, method, url, data, monkeypatch
):
    if url == "/images":
        _block_image_side_effects(monkeypatch)
    state_before = await _catalog_state(db)

    response = await _request(auth_ac, method, url, data)

    assert response.status_code == 403, response.text
    assert await _catalog_state(db) == state_before


@pytest.mark.parametrize(("method", "url", "data"), ADDITIONAL_ADMIN_ROUTES)
async def test_admin_can_reach_admin_only_routes(
    admin_ac, method, url, data, monkeypatch
):
    if url == "/images":
        from src.api import images

        monkeypatch.setattr(
            images, "open", lambda *args, **kwargs: BytesIO(), raising=False
        )
        monkeypatch.setattr(images.shutil, "copyfileobj", lambda *args, **kwargs: None)
        monkeypatch.setattr(images.resize_image, "delay", lambda *args, **kwargs: None)

    response = await _request(admin_ac, method, url, data)

    assert response.status_code not in (401, 403), response.text


@pytest.mark.parametrize(("method", "url", "data"), USER_ROUTES)
async def test_user_can_reach_authenticated_routes(
    auth_ac, db, user_data, method, url, data
):
    user = await db.session.scalar(
        select(UsersOrm).where(UsersOrm.email == user_data["email"])
    )
    assert user.role == UserRole.user

    response = await _request(auth_ac, method, url, data)

    assert response.status_code == 200, response.text


@pytest.mark.parametrize(("method", "url", "data"), USER_ROUTES)
async def test_admin_can_reach_authenticated_routes(
    admin_ac, db, user_data, method, url, data
):
    user = await db.session.scalar(
        select(UsersOrm).where(UsersOrm.email == user_data["email"])
    )
    assert user.role == UserRole.admin

    response = await _request(admin_ac, method, url, data)

    assert response.status_code == 200, response.text


@pytest.mark.parametrize(("method", "url", "data"), USER_ROUTES)
async def test_anonymous_cannot_reach_authenticated_routes(ac, method, url, data):
    response = await _request(ac, method, url, data)

    assert response.status_code == 401, response.text


async def test_catalog_get_routes_remain_public(ac):
    hotels = await ac.get(
        "/hotels", params={"date_from": "2030-08-01", "date_to": "2030-08-10"}
    )
    rooms = await ac.get("/rooms", params={"id": 1, "hotel_id": 1})
    available_rooms = await ac.get(
        "/rooms/1/rooms",
        params={"date_from": "2030-08-01", "date_to": "2030-08-10"},
    )
    facilities = await ac.get("/facilities/")
    assert (
        hotels.status_code
        == rooms.status_code
        == available_rooms.status_code
        == facilities.status_code
        == 200
    )
