from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import select, update

from src.model.users import UserRole, UsersOrm
from src.tasks.tasks import resize_image


@pytest.fixture
def png_upload():
    content = BytesIO()
    Image.new("RGB", (8, 8), "blue").save(content, format="PNG")
    content.seek(0)
    return {"file": ("admin-test.png", content, "image/png")}


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("delete", "/hotels/1", None),
        ("post", "/hotels", {"title": "New hotel", "location": "Test"}),
        ("put", "/hotels/1", {"title": "Updated hotel", "location": "Test"}),
        ("patch", "/hotels/1", {"title": "Updated hotel"}),
        (
            "post",
            "/rooms",
            {"hotel_id": 1, "title": "New room", "price": 100, "quantity": 1},
        ),
        ("delete", "/rooms/1", None),
        (
            "put",
            "/rooms/1/1",
            {
                "title": "Updated room",
                "description": "Test",
                "price": 100,
                "quantity": 1,
                "facilities_ids": [],
            },
        ),
        ("patch", "/rooms/1/1", {"price": 100}),
        ("post", "/facilities/", {"title": "New facility"}),
        ("get", "/booking", None),
    ],
)
async def test_regular_user_cannot_manage_admin_resources(
    auth_ac, method, path, body
):
    response = await auth_ac.request(method, path, json=body)

    assert response.status_code == 403, response.text


async def test_anonymous_user_cannot_upload_image(ac, png_upload, monkeypatch):
    monkeypatch.setattr(resize_image, "delay", lambda *_args, **_kwargs: None)

    response = await ac.post("/images", files=png_upload)

    assert response.status_code == 401, response.text


async def test_image_upload_requires_admin_role_from_database(
    auth_ac, db, png_upload, monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    queued = []
    monkeypatch.setattr(resize_image, "delay", lambda path: queued.append(path))
    user = await db.session.scalar(select(UsersOrm))
    await db.session.execute(
        update(UsersOrm).where(UsersOrm.id == user.id).values(role=UserRole.admin)
    )
    await db.commit()

    allowed = await auth_ac.post("/images", files=png_upload)

    assert allowed.status_code == 200, allowed.text
    assert queued == ["src/static/images/admin-test.png"]

    await db.session.execute(
        update(UsersOrm).where(UsersOrm.id == user.id).values(role=UserRole.user)
    )
    await db.commit()
    png_upload["file"][1].seek(0)
    denied = await auth_ac.post("/images", files=png_upload)

    assert denied.status_code == 403, denied.text
    assert queued == ["src/static/images/admin-test.png"]


async def test_new_accounts_are_regular_users(db, register_user, user_data):
    user = await db.session.scalar(
        select(UsersOrm).where(UsersOrm.email == user_data["email"])
    )

    assert user.role is UserRole.user


async def test_registration_cannot_assign_admin_role(ac, db, user_data):
    response = await ac.post("/users/auth", json={**user_data, "role": "admin"})
    assert response.status_code == 422, response.text
    assert await db.session.scalar(
        select(UsersOrm).where(UsersOrm.email == user_data["email"])
    ) is None


async def test_http_body_limit_rejects_large_image_request(ac, monkeypatch, tmp_path):
    from src.upload_limits import MAX_IMAGE_REQUEST_BYTES

    monkeypatch.chdir(tmp_path)
    response = await ac.post(
        "/images",
        files={
            "file": (
                "too-large.png",
                b"x" * (MAX_IMAGE_REQUEST_BYTES + 1),
                "image/png",
            )
        },
    )

    assert response.status_code == 413, response.text
    assert not (tmp_path / "src" / "static" / "images" / "too-large.png").exists()


async def test_image_upload_does_not_overwrite_existing_file(
    auth_ac, db, png_upload, monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(resize_image, "delay", lambda *_args, **_kwargs: None)
    user = await db.session.scalar(select(UsersOrm))
    await db.session.execute(
        update(UsersOrm).where(UsersOrm.id == user.id).values(role=UserRole.admin)
    )
    await db.commit()
    image_path = tmp_path / "src" / "static" / "images" / "admin-test.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"keep this file")

    response = await auth_ac.post("/images", files=png_upload)

    assert response.status_code == 409, response.text
    assert image_path.read_bytes() == b"keep this file"
