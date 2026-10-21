from datetime import datetime, timedelta, timezone
import asyncio
from threading import Event, Timer

import jwt
import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from passlib.context import CryptContext
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError

from src.FastApiOb import app
from src.api.dependencies import get_current_user, require_admin
from src.config import settings
from src.model.users import UserRole, UsersOrm
from src.serves.auth import AuthService


async def test_registration_persists_user_and_password_hash(ac, db, user_data):
    response = await ac.post("/users/auth", json=user_data)

    assert response.status_code == 200
    assert response.json() == {"status": "OK"}
    assert "access_token" not in ac.cookies
    user = await db.users.get_user_with_hashed(email=user_data["email"])
    assert user is not None
    assert user.id > 0
    assert user.model_dump(exclude={"id", "hashed_password", "role"}) == {
        key: value for key, value in user_data.items() if key != "password"
    }
    assert await db.session.scalar(
        select(UsersOrm.role).where(UsersOrm.id == user.id)
    ) is UserRole.user
    assert user.hashed_password != user_data["password"]
    assert AuthService().verify_password(user_data["password"], user.hashed_password)
    assert not AuthService().verify_password("different-password", user.hashed_password)


async def test_registration_cannot_assign_admin_role(ac, db, user_data):
    response = await ac.post("/users/auth", json={**user_data, "role": "admin"})

    assert response.status_code == 422
    assert any(error["loc"] == ["body", "role"] for error in response.json()["detail"])
    assert await db.users.get_all() == []


async def test_registration_assigns_user_role_and_profile_hides_it(ac, db, user_data):
    response = await ac.post("/users/auth", json=user_data)

    assert response.status_code == 200
    user = (
        await db.session.execute(
            select(UsersOrm).where(UsersOrm.email == user_data["email"])
        )
    ).scalar_one()
    assert user.role == "user"

    login = await ac.post(
        "/users/login",
        json={"email": user_data["email"], "password": user_data["password"]},
    )
    assert login.status_code == 200
    profile = await ac.get("/users/only_auth")
    assert profile.status_code == 200
    assert "role" not in profile.json()


async def test_user_role_server_default_is_applied_without_insert_value(db):
    role = await db.session.scalar(
        text(
            """INSERT INTO users
               (email, hashed_password, number, first_name, second_name, sex)
               VALUES ('default-role@example.com', 'hash', '+79999999999',
                       'Test', 'User', 'female')
               RETURNING role"""
        )
    )

    assert role == "user"


async def test_postgresql_rejects_unknown_user_role_without_poisoning_session(db):
    with pytest.raises(DBAPIError):
        async with db.session.begin_nested():
            await db.session.execute(
                text(
                    """INSERT INTO users
                       (email, hashed_password, number, first_name, second_name,
                        sex, role)
                       VALUES ('invalid-role@example.com', 'hash', '+79999999999',
                               'Test', 'User', 'female', 'owner')"""
                )
            )

    assert await db.session.scalar(text("SELECT 1")) == 1


async def test_login_returns_token_and_sets_cookie(ac, register_user, db, user_data):
    response = await ac.post(
        "/users/login",
        json={"email": user_data["email"], "password": user_data["password"]},
    )

    assert response.status_code == 200
    token = response.json()["access_token"]
    assert response.json() == {"access_token": token}
    assert isinstance(token, str) and token
    assert ac.cookies["access_token"] == token
    assert "access_token=" in response.headers["set-cookie"]
    assert "Path=/" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "samesite=lax" in response.headers["set-cookie"].lower()
    assert f"Max-Age={settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60}" in response.headers["set-cookie"]
    assert "Secure" not in response.headers["set-cookie"]
    user = await db.users.get_user_with_hashed(email=user_data["email"])
    payload = AuthService().decode_token(token)
    assert payload["user_id"] == user.id
    assert payload["exp"] > datetime.now(timezone.utc).timestamp()


@pytest.mark.parametrize("path", ["/users/auth", "/users/login"])
async def test_password_cannot_be_empty(ac, db, user_data, path):
    data = user_data if path == "/users/auth" else {
        "email": user_data["email"], "password": ""
    }
    response = await ac.post(path, json={**data, "password": ""})

    assert response.status_code == 422
    assert any(error["loc"] == ["body", "password"] for error in response.json()["detail"])
    assert await db.users.get_all() == []


async def test_login_with_bcrypt_password_containing_nul_returns_401(
    ac, register_user, db, user_data
):
    legacy_hash = CryptContext(schemes=["bcrypt"]).hash("legacy password")
    await db.session.execute(
        update(UsersOrm)
        .where(UsersOrm.email == user_data["email"])
        .values(hashed_password=legacy_hash)
    )
    await db.commit()

    response = await ac.post(
        "/users/login",
        json={"email": user_data["email"], "password": "legacy password\u0000tail"},
    )

    assert response.status_code == 401
    assert "access_token" not in ac.cookies


async def test_login_with_pbkdf2_password_containing_nul_succeeds(ac, db, user_data):
    password = "legacy\u0000password"
    registration = await ac.post(
        "/users/auth", json={**user_data, "password": password}
    )
    assert registration.status_code == 200, registration.text

    response = await ac.post(
        "/users/login", json={"email": user_data["email"], "password": password}
    )

    assert response.status_code == 200, response.text
    assert response.json()["access_token"]


@pytest.mark.parametrize("operation", ["hash", "verify"])
async def test_password_work_does_not_block_async_pulse(
    ac, user_data, monkeypatch, operation
):
    if operation == "verify":
        registration = await ac.post("/users/auth", json=user_data)
        assert registration.status_code == 200, registration.text

    entered = Event()
    released = Event()
    finished = Event()
    pulse_ran_while_blocked = False
    service = AuthService()
    method_name = "hashed_password" if operation == "hash" else "verify_password"
    original = getattr(service, method_name)

    def controlled_password_work(*args):
        entered.set()
        try:
            released.wait()
            return original(*args)
        finally:
            finished.set()

    monkeypatch.setattr(
        AuthService, method_name, lambda self, *args: controlled_password_work(*args)
    )
    timer = Timer(1, released.set)
    timer.start()
    try:
        if operation == "hash":
            request = asyncio.create_task(ac.post("/users/auth", json=user_data))
        else:
            request = asyncio.create_task(
                ac.post(
                    "/users/login",
                    json={"email": user_data["email"], "password": user_data["password"]},
                )
            )
        assert await asyncio.to_thread(entered.wait, 2)

        async def pulse():
            nonlocal pulse_ran_while_blocked
            pulse_ran_while_blocked = not finished.is_set()
            released.set()

        await pulse()
        response = await request
    finally:
        released.set()
        timer.cancel()

    assert pulse_ran_while_blocked
    assert response.status_code == 200, response.text


async def test_login_cookie_is_secure_in_production(
    ac, register_user, user_data, monkeypatch
):
    monkeypatch.setattr(settings, "MODE", "PROD")
    response = await ac.post(
        "/users/login",
        json={"email": user_data["email"], "password": user_data["password"]},
    )

    assert response.status_code == 200
    assert "Secure" in response.headers["set-cookie"]


async def test_authenticated_profile_does_not_expose_password(auth_ac, db, user_data):
    response = await auth_ac.get("/users/only_auth")

    assert response.status_code == 200
    user = await db.users.get_user_with_hashed(email=user_data["email"])
    assert response.json() == user.model_dump(exclude={"hashed_password"})
    assert "hashed_password" not in response.json()
    assert "password" not in response.json()


async def test_logout_removes_cookie_and_revokes_client_access(auth_ac):
    response = await auth_ac.post("/users/out_system")

    assert response.status_code == 200
    assert response.json() == {"status": "Ok"}
    assert "access_token" not in auth_ac.cookies
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert (await auth_ac.get("/users/only_auth")).status_code == 401


async def test_anonymous_profile_is_rejected(ac):
    response = await ac.get("/users/only_auth")

    assert response.status_code == 401
    assert response.json() == {"detail": "Вы не предоставили токен доступа"}


@pytest.mark.parametrize(
    "field", ["email", "password", "number", "first_name", "second_name", "sex"]
)
async def test_registration_requires_each_field(ac, db, user_data, field):
    data = user_data.copy()
    del data[field]

    response = await ac.post("/users/auth", json=data)

    assert response.status_code == 422
    assert any(error["loc"] == ["body", field] for error in response.json()["detail"])
    assert await db.users.get_all() == []


@pytest.mark.parametrize(
    "field,value",
    [("email", "not-an-email"), ("email", "user@"), ("sex", "other"), ("sex", "Male")],
)
async def test_registration_rejects_invalid_email_and_sex(
    ac, db, user_data, field, value
):
    response = await ac.post("/users/auth", json={**user_data, field: value})

    assert response.status_code == 422
    assert any(error["loc"] == ["body", field] for error in response.json()["detail"])
    assert await db.users.get_all() == []


@pytest.mark.parametrize("field", ["first_name", "second_name"])
async def test_registration_rejects_names_longer_than_database_column(
    ac, db, user_data, field
):
    response = await ac.post("/users/auth", json={**user_data, field: "n" * 21})

    assert response.status_code == 422
    assert any(error["loc"] == ["body", field] for error in response.json()["detail"])
    assert await db.users.get_all() == []


@pytest.mark.parametrize("field", ["email", "number", "first_name", "second_name"])
async def test_registration_rejects_nul_in_stored_text_fields(ac, db, user_data, field):
    response = await ac.post("/users/auth", json={**user_data, field: f"x\u0000tail"})

    assert response.status_code == 422, response.text
    assert any(error["loc"] == ["body", field] for error in response.json()["detail"])
    assert await db.users.get_all() == []


async def test_registration_rejects_email_longer_than_database_column(ac, db, user_data):
    long_but_valid_email = f'{"a" * 64}@{"b" * 63}.com'
    assert len(long_but_valid_email) > 100

    response = await ac.post("/users/auth", json={**user_data, "email": long_but_valid_email})

    assert response.status_code == 422
    assert any(error["loc"] == ["body", "email"] for error in response.json()["detail"])
    assert await db.users.get_all() == []


async def test_registration_rejects_password_over_passlib_limit(ac, db, user_data):
    response = await ac.post("/users/auth", json={**user_data, "password": "p" * 4097})

    assert response.status_code == 422
    assert any(error["loc"] == ["body", "password"] for error in response.json()["detail"])
    assert await db.users.get_all() == []


async def test_registration_accepts_password_at_passlib_limit(ac, db, user_data):
    password = "p" * 4096
    response = await ac.post("/users/auth", json={**user_data, "password": password})

    assert response.status_code == 200, response.text
    saved = await db.users.get_user_with_hashed(email=user_data["email"])
    assert saved is not None
    assert AuthService().verify_password(password, saved.hashed_password)


@pytest.mark.parametrize(
    "number", ["abc", "+123", "+1234567890123456", "+7-999-999-9999"]
)
async def test_registration_rejects_invalid_phone(ac, db, user_data, number):
    response = await ac.post("/users/auth", json={**user_data, "number": number})

    assert response.status_code == 422
    assert any(
        error["loc"] == ["body", "number"] for error in response.json()["detail"]
    )
    assert await db.users.get_all() == []


@pytest.mark.parametrize("field", ["email", "password"])
async def test_login_requires_each_field(ac, user_data, field):
    data = {"email": user_data["email"], "password": user_data["password"]}
    del data[field]

    response = await ac.post("/users/login", json=data)

    assert response.status_code == 422
    assert any(error["loc"] == ["body", field] for error in response.json()["detail"])
    assert "access_token" not in ac.cookies


async def test_login_rejects_invalid_email(ac):
    response = await ac.post(
        "/users/login", json={"email": "not-an-email", "password": "string"}
    )

    assert response.status_code == 422
    assert any(error["loc"] == ["body", "email"] for error in response.json()["detail"])
    assert "access_token" not in ac.cookies


async def test_login_rejects_password_over_passlib_limit(ac, register_user, user_data):
    response = await ac.post(
        "/users/login", json={"email": user_data["email"], "password": "p" * 4097}
    )

    assert response.status_code == 422
    assert any(error["loc"] == ["body", "password"] for error in response.json()["detail"])
    assert "access_token" not in ac.cookies


async def test_login_accepts_password_at_passlib_limit(ac, db, user_data):
    password = "p" * 4096
    registration = await ac.post(
        "/users/auth", json={**user_data, "password": password}
    )
    assert registration.status_code == 200, registration.text

    response = await ac.post(
        "/users/login", json={"email": user_data["email"], "password": password}
    )

    assert response.status_code == 200, response.text
    saved = await db.users.get_user_with_hashed(email=user_data["email"])
    assert saved is not None
    assert AuthService().verify_password(password, saved.hashed_password)
    assert response.json()["access_token"]


@pytest.mark.parametrize(
    "email,password,detail",
    [
        ("user@example.com", "wrong-password", "Неправильный пароль"),
        ("missing@example.com", "string", "Пользователя с таким email не существует"),
    ],
)
async def test_login_rejects_wrong_credentials(
    ac, register_user, email, password, detail
):
    response = await ac.post(
        "/users/login", json={"email": email, "password": password}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": detail}
    assert "access_token" not in ac.cookies


async def test_authentication_cookie_is_isolated_between_clients(auth_ac):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as other:
        assert not other.cookies
        assert (await other.get("/users/only_auth")).status_code == 401
        assert (await auth_ac.get("/users/only_auth")).status_code == 200
        await other.post("/users/out_system")
        assert (await auth_ac.get("/users/only_auth")).status_code == 200


async def test_duplicate_email_preserves_original_user(
    ac, register_user, db, user_data
):
    original = await db.users.get_user_with_hashed(email=user_data["email"])
    original_data = original.model_dump()
    duplicate_data = {
        **user_data,
        "password": "replacement-password",
        "number": "+78888888888",
        "first_name": "replacement",
        "second_name": "replacement",
        "sex": "female",
    }

    response = await ac.post("/users/auth", json=duplicate_data)

    saved = await db.users.get_user_with_hashed(email=user_data["email"])
    assert saved is not None
    assert saved.model_dump() == original_data
    users = (await db.session.execute(select(UsersOrm))).scalars().all()
    assert len(users) == 1
    assert response.status_code == 409
    assert isinstance(response.json()["detail"], str)


@pytest.mark.parametrize(
    "token_kind",
    [
        "malformed",
        "wrong_key",
        "expired",
        "missing_user_id",
        "missing_exp",
        "list_exp",
        "dict_exp",
        "infinite_exp",
        "oversized_user_id",
    ],
)
async def test_profile_rejects_invalid_tokens(
    ac, register_user, db, user_data, token_kind
):
    user = await db.users.get_user_with_hashed(email=user_data["email"])
    payload = {
        "user_id": user.id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    key = settings.JWT_SECRET_KEY
    if token_kind == "expired":
        payload["exp"] = datetime.now(timezone.utc) - timedelta(minutes=1)
    elif token_kind == "missing_user_id":
        del payload["user_id"]
    elif token_kind == "invalid_user_id":
        payload["user_id"] = str(user.id)
    elif token_kind == "missing_exp":
        del payload["exp"]
    elif token_kind == "list_exp":
        payload["exp"] = []
    elif token_kind == "dict_exp":
        payload["exp"] = {}
    elif token_kind == "infinite_exp":
        payload["exp"] = float("inf")
    elif token_kind == "oversized_user_id":
        payload["user_id"] = 2147483648
    elif token_kind == "wrong_key":
        key = "integration-test-key-that-is-not-the-application-key"
    token = (
        "not-a-jwt"
        if token_kind == "malformed"
        else jwt.encode(payload, key, algorithm=settings.JWT_ALGORITHM)
    )
    ac.cookies.set("access_token", token)

    response = await ac.get("/users/only_auth")

    assert response.status_code == 401
    assert isinstance(response.json()["detail"], str)


async def test_profile_rejects_token_for_deleted_user(auth_ac, db, user_data):
    user = await db.users.get_user_with_hashed(email=user_data["email"])
    await db.users.delete(id=user.id)
    await db.commit()

    response = await auth_ac.get("/users/only_auth")

    assert response.status_code == 401
    assert isinstance(response.json()["detail"], str)


async def test_current_role_is_loaded_from_database_for_same_token(
    auth_ac, db, user_data
):
    user = await db.users.get_user_with_hashed(email=user_data["email"])
    token = auth_ac.cookies["access_token"]

    user_row = await db.users.get_one_or_none(id=user.id)
    user_row.role = UserRole.user
    await db.commit()
    current_user = await get_current_user(db=db, token=token)
    with pytest.raises(HTTPException) as error:
        await require_admin(current_user=current_user)
    assert error.value.status_code == 403

    user_row.role = UserRole.admin
    await db.commit()
    current_user = await get_current_user(db=db, token=token)
    assert await require_admin(current_user=current_user) is current_user

    user_row.role = UserRole.user
    await db.commit()
    current_user = await get_current_user(db=db, token=token)
    with pytest.raises(HTTPException) as error:
        await require_admin(current_user=current_user)
    assert error.value.status_code == 403
    assert (await auth_ac.get("/users/only_auth")).status_code == 200
